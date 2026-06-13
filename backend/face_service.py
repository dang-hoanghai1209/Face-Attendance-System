import io
import math
import os
import pickle
from threading import Lock

from PIL import Image
import torch
import torch.nn.functional as torch_functional
from facenet_pytorch import InceptionResnetV1, MTCNN
from facenet_pytorch.models.mtcnn import extract_face, fixed_image_standardization

from models.face_embedding import FaceEmbedding
from models.student import Student


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model_lock = Lock()
_detector = None
_embedder = None


def _parse_float_env(name, default, minimum=None, maximum=None):
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default
    if not math.isfinite(value):
        value = default

    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


THRESHOLD_CONFIRM = min(max(float(os.getenv("THRESHOLD_CONFIRM", "0.75")), 0.0), 1.0)
THRESHOLD_UNCERTAIN = min(max(float(os.getenv("THRESHOLD_UNCERTAIN", "0.60")), 0.0), 1.0)
ENABLE_LEGACY_EMBEDDINGS = os.getenv("ENABLE_LEGACY_EMBEDDINGS", "false").lower() == "true"
MAX_RECOGNITION_FACES = 4
ENABLE_LIVENESS = os.getenv("ENABLE_LIVENESS", "false").lower() in {"1", "true", "yes", "on"}
LIVENESS_THRESHOLD = _parse_float_env("LIVENESS_THRESHOLD", 0.80, minimum=0.0, maximum=1.0)
LIVENESS_MODEL = os.getenv("LIVENESS_MODEL", "minifasnet")


def face_models_loaded():
    return _detector is not None and _embedder is not None


def get_face_models():
    global _detector, _embedder

    if face_models_loaded():
        return _detector, _embedder

    with _model_lock:
        if not face_models_loaded():
            _detector = MTCNN(keep_all=False, device=device)
            _embedder = InceptionResnetV1(pretrained="vggface2").eval().to(device)

    return _detector, _embedder


def load_legacy_embeddings(db_path):
    if not os.path.exists(db_path):
        return {}

    with open(db_path, "rb") as db_file:
        raw_data = pickle.load(db_file)

    normalized = {}
    for student_code, value in raw_data.items():
        tensors = []
        if isinstance(value, dict):
            for item in value.values():
                if torch.is_tensor(item):
                    tensors.append(item.detach().cpu().reshape(-1))
        elif torch.is_tensor(value):
            tensors.append(value.detach().cpu().reshape(-1))

        if tensors:
            normalized[student_code] = tensors

    return normalized


def image_bytes_to_embedding(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    detector, embedder = get_face_models()
    face = detector(image)
    if face is None:
        return None

    with torch.inference_mode():
        embedding = embedder(face.unsqueeze(0).to(device)).detach().cpu().reshape(-1)
    return embedding


def check_liveness(image_bytes: bytes) -> dict:
    if not ENABLE_LIVENESS:
        return {
            "liveness_passed": True,
            "score": None,
            "label": "disabled",
        }

    return {
        "liveness_passed": False,
        "score": None,
        "label": "unavailable",
        "model": LIVENESS_MODEL,
        "threshold": LIVENESS_THRESHOLD,
        "message": "Liveness model is not available.",
    }


def _bbox_from_box(box, image_size):
    image_width, image_height = image_size
    x1, y1, x2, y2 = [float(value) for value in box]
    x1 = max(0.0, min(x1, image_width))
    y1 = max(0.0, min(y1, image_height))
    x2 = max(0.0, min(x2, image_width))
    y2 = max(0.0, min(y2, image_height))
    return {
        "x": int(round(x1)),
        "y": int(round(y1)),
        "w": int(round(max(x2 - x1, 0.0))),
        "h": int(round(max(y2 - y1, 0.0))),
    }


def image_bytes_to_face_embeddings(image_bytes, max_faces=MAX_RECOGNITION_FACES):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    detector, embedder = get_face_models()
    boxes, probs = detector.detect(image)
    if boxes is None:
        return []

    face_items = []
    for index, box in enumerate(boxes):
        probability = probs[index] if probs is not None else 0.0
        face_items.append((probability if probability is not None else 0.0, box))
    face_items.sort(key=lambda item: item[0], reverse=True)
    selected_boxes = [box for _probability, box in face_items[:max_faces]]
    if not selected_boxes:
        return []

    face_tensors = []
    for box in selected_boxes:
        face = extract_face(image, box, detector.image_size, detector.margin, save_path=None)
        if detector.post_process:
            face = fixed_image_standardization(face)
        face_tensors.append(face)
    if not face_tensors:
        return []
    faces = torch.stack(face_tensors)

    with torch.inference_mode():
        embeddings = embedder(faces.to(device)).detach().cpu()

    results = []
    for index, box in enumerate(selected_boxes):
        results.append(
            {
                "embedding": embeddings[index].reshape(-1),
                "bbox": _bbox_from_box(box, image.size),
            }
        )
    return results


def count_faces_in_image_bytes(image_bytes):
    image = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    detector, _embedder = get_face_models()
    boxes, _probs = detector.detect(image)
    return 0 if boxes is None else len(boxes)


def aggregate_embeddings(embeddings):
    if not embeddings:
        return None

    stacked = torch.stack(embeddings)
    return stacked.mean(dim=0)


def serialize_embedding(embedding_tensor):
    return pickle.dumps(embedding_tensor.tolist())


def deserialize_embedding(embedding_bytes):
    values = pickle.loads(embedding_bytes)
    return torch.tensor(values, dtype=torch.float32)


def cosine_similarity(first_embedding, second_embedding):
    return torch_functional.cosine_similarity(
        first_embedding.unsqueeze(0),
        second_embedding.unsqueeze(0),
    ).item()


def match_embedding(embedding, db_embeddings, legacy_embeddings=None, include_legacy=False):
    best_score = -1.0
    best_student_code = "Unknown"

    for record, student in db_embeddings:
        db_tensor = deserialize_embedding(record.embedding_data)
        score = cosine_similarity(embedding, db_tensor)
        if score > best_score:
            best_score = score
            best_student_code = student.student_code

    if include_legacy and legacy_embeddings:
        for student_code, tensors in legacy_embeddings.items():
            for tensor in tensors:
                score = cosine_similarity(embedding, tensor)
                if score > best_score:
                    best_score = score
                    best_student_code = student_code

    rounded_score = round(best_score, 4)

    if best_score >= THRESHOLD_CONFIRM:
        return "success", best_student_code, rounded_score

    if best_score >= THRESHOLD_UNCERTAIN:
        return "uncertain", best_student_code, rounded_score

    return "unknown", "Unknown", rounded_score


def fetch_db_embeddings(db_session):
    return (
        db_session.query(FaceEmbedding, Student)
        .join(Student, Student.id == FaceEmbedding.student_id)
        .all()
    )


def replace_student_embeddings(db_session, student_id, embeddings, source="webcam"):
    db_session.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id).delete()

    for embedding in embeddings:
        db_session.add(
            FaceEmbedding(
                student_id=student_id,
                embedding_data=serialize_embedding(embedding),
                source=source,
            )
        )

    db_session.commit()


def embedding_count(db_session, student_id):
    return db_session.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id).count()
