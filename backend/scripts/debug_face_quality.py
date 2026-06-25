import argparse
from dataclasses import asdict
import json
import sys
from pathlib import Path

from PIL import Image
import torch
from facenet_pytorch import MTCNN


BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from services.face_quality_service import (  # noqa: E402
    METRIC_DESCRIPTIONS,
    calculate_brightness,
    calculate_sharpness,
    evaluate_face_quality,
    load_face_quality_thresholds_from_env,
)


def _to_plain_list(value):
    if value is None:
        return None
    return [[round(float(coord), 4) for coord in point] for point in value]


def _bbox_to_plain_list(value):
    if value is None:
        return None
    return [round(float(coord), 4) for coord in value]


def _face_candidate(index, box, probability):
    return {
        "index": index,
        "bbox": _bbox_to_plain_list(box),
        "detection_probability": round(float(probability or 0.0), 4),
    }


def analyze_image(image_path: Path) -> dict:
    image = Image.open(image_path).convert("RGB")
    thresholds = load_face_quality_thresholds_from_env()
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    detector = MTCNN(keep_all=True, device=device)
    boxes, probabilities, landmarks = detector.detect(image, landmarks=True)

    if boxes is None or len(boxes) == 0:
        return {
            "image_path": str(image_path),
            "image_size": {"width": image.size[0], "height": image.size[1]},
            "thresholds": asdict(thresholds),
            "metric_descriptions": METRIC_DESCRIPTIONS,
            "face_detected": False,
            "face_count": 0,
            "selected_face_index": None,
            "all_faces": [],
            "bbox": None,
            "detection_probability": None,
            "landmarks": None,
            "sharpness": calculate_sharpness(image),
            "brightness": calculate_brightness(image),
            "face_size_ratio": None,
            "yaw_estimate": None,
            "landmark_geometry_valid": False,
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
    quality = evaluate_face_quality(image, bbox, probability, face_landmarks, thresholds=thresholds)

    return {
        "image_path": str(image_path),
        "image_size": {"width": image.size[0], "height": image.size[1]},
        "thresholds": asdict(thresholds),
        "metric_descriptions": METRIC_DESCRIPTIONS,
        "face_detected": True,
        "face_count": len(boxes),
        "selected_face_index": int(index),
        "all_faces": [
            _face_candidate(candidate_index, candidate_box, probabilities[candidate_index] if probabilities is not None else 0.0)
            for candidate_index, candidate_box in enumerate(boxes)
        ],
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
    output_group = parser.add_mutually_exclusive_group()
    output_group.add_argument("--pretty", action="store_true", help="Print indented JSON output. This is the default.")
    output_group.add_argument("--json-only", action="store_true", help="Print compact JSON without extra whitespace.")
    args = parser.parse_args()

    image_path = Path(args.image_path)
    if not image_path.exists():
        print(f"Image not found: {image_path}", file=sys.stderr)
        return 2

    result = analyze_image(image_path)
    indent = None if args.json_only else 2
    print(json.dumps(result, indent=indent, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
