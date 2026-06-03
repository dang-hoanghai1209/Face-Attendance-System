import io
import os
import pickle
from threading import Lock

from PIL import Image
import torch
import torch.nn.functional as torch_functional
from facenet_pytorch import InceptionResnetV1, MTCNN

from models.face_embedding import FaceEmbedding
from models.student import Student


device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
_model_lock = Lock()
_detector = None
_embedder = None

THRESHOLD_CONFIRM = min(max(float(os.getenv("THRESHOLD_CONFIRM", "0.75")), 0.0), 1.0)
THRESHOLD_UNCERTAIN = min(max(float(os.getenv("THRESHOLD_UNCERTAIN", "0.60")), 0.0), 1.0)
ENABLE_LEGACY_EMBEDDINGS = os.getenv("ENABLE_LEGACY_EMBEDDINGS", "false").lower() == "true"


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
