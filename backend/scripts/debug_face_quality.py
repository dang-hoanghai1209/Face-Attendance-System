import argparse
import json
import sys
from pathlib import Path

from PIL import Image
import torch
from facenet_pytorch import MTCNN


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.face_quality_service import evaluate_face_quality  # noqa: E402


def _to_plain_list(value):
    if value is None:
        return None
    return [[round(float(coord), 4) for coord in point] for point in value]


def _bbox_to_plain_list(value):
    if value is None:
        return None
    return [round(float(coord), 4) for coord in value]


def analyze_image(image_path: Path) -> dict:
    image = Image.open(image_path).convert("RGB")
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    detector = MTCNN(keep_all=True, device=device)
    boxes, probabilities, landmarks = detector.detect(image, landmarks=True)

    if boxes is None or len(boxes) == 0:
        return {
            "face_detected": False,
            "bbox": None,
            "detection_probability": None,
            "landmarks": None,
            "sharpness": None,
            "brightness": None,
            "face_size_ratio": None,
            "yaw_estimate": None,
            "reason_code": "FACE_NOT_DETECTED",
            "final_result": "FACE_UNCLEAR",
        }

    face_items = []
    for index, box in enumerate(boxes):
        probability = probabilities[index] if probabilities is not None else 0.0
        face_items.append((float(probability or 0.0), index, box))
    face_items.sort(key=lambda item: item[0], reverse=True)

    probability, index, bbox = face_items[0]
    face_landmarks = landmarks[index] if landmarks is not None else None
    quality = evaluate_face_quality(image, bbox, probability, face_landmarks)

    return {
        "face_detected": True,
        "bbox": _bbox_to_plain_list(bbox),
        "detection_probability": round(probability, 4),
        "landmarks": _to_plain_list(face_landmarks),
        "sharpness": quality.metrics.sharpness,
        "brightness": quality.metrics.brightness,
        "face_size_ratio": quality.metrics.face_size_ratio,
        "yaw_estimate": quality.metrics.yaw_estimate,
        "landmark_geometry_valid": quality.metrics.landmark_geometry_valid,
        "reason_code": quality.reason_code,
        "final_result": quality.final_result,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Debug Face Quality Gate for one image.")
    parser.add_argument("image_path", help="Path to an image file.")
    args = parser.parse_args()

    image_path = Path(args.image_path)
    if not image_path.exists():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 2

    result = analyze_image(image_path)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
