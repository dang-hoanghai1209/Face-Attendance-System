from dataclasses import dataclass
from enum import Enum
import os
from typing import Optional, Sequence

import numpy as np
from PIL import Image, ImageFilter, ImageStat


DEFAULT_MIN_SHARPNESS = 8.0
DEFAULT_MIN_BRIGHTNESS = 45.0
DEFAULT_MAX_BRIGHTNESS = 220.0
DEFAULT_MIN_FACE_SIZE_RATIO = 0.08
DEFAULT_MIN_DETECTION_PROBABILITY = 0.90
DEFAULT_MAX_YAW_RATIO = 0.35


class FaceQualityReason(str, Enum):
    LOW_SHARPNESS = "LOW_SHARPNESS"
    LOW_BRIGHTNESS = "LOW_BRIGHTNESS"
    HIGH_BRIGHTNESS = "HIGH_BRIGHTNESS"
    FACE_TOO_SMALL = "FACE_TOO_SMALL"
    POSE_OUT_OF_RANGE = "POSE_OUT_OF_RANGE"
    LANDMARK_MISSING = "LANDMARK_MISSING"
    LANDMARK_GEOMETRY_INVALID = "LANDMARK_GEOMETRY_INVALID"
    LOW_DETECTION_CONFIDENCE = "LOW_DETECTION_CONFIDENCE"
    LOW_FACE_QUALITY = "LOW_FACE_QUALITY"


@dataclass(frozen=True)
class FaceQualityThresholds:
    """Calibration knobs for the debug Face Quality Gate.

    These defaults are starting points only. They should be calibrated with
    real capture samples before this gate is used in production attendance.
    Environment variables with the FACE_QUALITY_* prefix can override them.
    """

    min_sharpness: float = DEFAULT_MIN_SHARPNESS
    min_brightness: float = DEFAULT_MIN_BRIGHTNESS
    max_brightness: float = DEFAULT_MAX_BRIGHTNESS
    min_face_size_ratio: float = DEFAULT_MIN_FACE_SIZE_RATIO
    min_detection_probability: float = DEFAULT_MIN_DETECTION_PROBABILITY
    max_yaw_ratio: float = DEFAULT_MAX_YAW_RATIO


@dataclass(frozen=True)
class FaceQualityMetrics:
    sharpness: float
    brightness: float
    face_size_ratio: float
    yaw_estimate: Optional[float]
    landmark_geometry_valid: bool


METRIC_DESCRIPTIONS = {
    "sharpness": "Variance of edge intensity from a grayscale image. Lower values usually mean blur or weak detail.",
    "brightness": "Mean grayscale pixel value from 0 to 255. Very low is dark; very high can be overexposed.",
    "face_size_ratio": "Detected face bounding-box area divided by full image area.",
    "detection_confidence": "MTCNN face detection probability for the selected face.",
    "yaw_estimate": "Approximate horizontal pose from nose offset relative to eye center and eye distance.",
    "landmark_geometry": "Neutral sanity checks for five MTCNN landmarks: eye, nose, and mouth ordering/spacing.",
}


@dataclass(frozen=True)
class FaceQualityResult:
    passed: bool
    final_result: str
    reason_code: Optional[str]
    metrics: FaceQualityMetrics


def _parse_float_env(name: str, default: float, minimum: Optional[float] = None, maximum: Optional[float] = None) -> float:
    try:
        value = float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        value = default

    if not np.isfinite(value):
        value = default
    if minimum is not None:
        value = max(value, minimum)
    if maximum is not None:
        value = min(value, maximum)
    return value


def load_face_quality_thresholds_from_env() -> FaceQualityThresholds:
    return FaceQualityThresholds(
        min_sharpness=_parse_float_env("FACE_QUALITY_MIN_SHARPNESS", DEFAULT_MIN_SHARPNESS, minimum=0.0),
        min_brightness=_parse_float_env(
            "FACE_QUALITY_MIN_BRIGHTNESS",
            DEFAULT_MIN_BRIGHTNESS,
            minimum=0.0,
            maximum=255.0,
        ),
        max_brightness=_parse_float_env(
            "FACE_QUALITY_MAX_BRIGHTNESS",
            DEFAULT_MAX_BRIGHTNESS,
            minimum=0.0,
            maximum=255.0,
        ),
        min_face_size_ratio=_parse_float_env(
            "FACE_QUALITY_MIN_FACE_SIZE_RATIO",
            DEFAULT_MIN_FACE_SIZE_RATIO,
            minimum=0.0,
            maximum=1.0,
        ),
        min_detection_probability=_parse_float_env(
            "FACE_QUALITY_MIN_DETECTION_PROBABILITY",
            DEFAULT_MIN_DETECTION_PROBABILITY,
            minimum=0.0,
            maximum=1.0,
        ),
        max_yaw_ratio=_parse_float_env("FACE_QUALITY_MAX_YAW_RATIO", DEFAULT_MAX_YAW_RATIO, minimum=0.0),
    )


DEFAULT_FACE_QUALITY_THRESHOLDS = FaceQualityThresholds()


def calculate_sharpness(image: Image.Image) -> float:
    """Return edge-variance sharpness; low values are useful for blur calibration."""
    grayscale = image.convert("L")
    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    values = np.asarray(edges, dtype=np.float32)
    return round(float(values.var()), 4)


def calculate_brightness(image: Image.Image) -> float:
    """Return mean grayscale brightness on the 0-255 pixel scale."""
    grayscale = image.convert("L")
    return round(float(ImageStat.Stat(grayscale).mean[0]), 4)


def calculate_face_size_ratio(bbox: Sequence[float], image_size: tuple[int, int]) -> float:
    """Return detected face area divided by image area."""
    image_width, image_height = image_size
    if image_width <= 0 or image_height <= 0:
        return 0.0

    x1, y1, x2, y2 = [float(value) for value in bbox]
    face_width = max(x2 - x1, 0.0)
    face_height = max(y2 - y1, 0.0)
    image_area = float(image_width * image_height)
    return round((face_width * face_height) / image_area, 4)


def normalize_landmarks(landmarks: Optional[Sequence[Sequence[float]]]) -> Optional[np.ndarray]:
    if landmarks is None:
        return None

    points = np.asarray(landmarks, dtype=np.float32)
    if points.shape != (5, 2) or not np.isfinite(points).all():
        return None
    return points


def estimate_yaw_from_landmarks(landmarks: Optional[Sequence[Sequence[float]]]) -> Optional[float]:
    """Estimate horizontal pose from five landmarks; this is only a calibration heuristic."""
    points = normalize_landmarks(landmarks)
    if points is None:
        return None

    left_eye, right_eye, nose = points[0], points[1], points[2]
    eye_distance = float(np.linalg.norm(right_eye - left_eye))
    if eye_distance <= 0:
        return None

    eye_center_x = float((left_eye[0] + right_eye[0]) / 2.0)
    return round(float((nose[0] - eye_center_x) / eye_distance), 4)


def validate_landmark_geometry(landmarks: Optional[Sequence[Sequence[float]]]) -> bool:
    """Validate neutral five-point landmark ordering and spacing without inferring identity or mask use."""
    points = normalize_landmarks(landmarks)
    if points is None:
        return False

    left_eye, right_eye, nose, left_mouth, right_mouth = points
    eye_distance = float(np.linalg.norm(right_eye - left_eye))
    mouth_distance = float(np.linalg.norm(right_mouth - left_mouth))
    if eye_distance <= 0 or mouth_distance <= 0:
        return False

    eye_center_y = float((left_eye[1] + right_eye[1]) / 2.0)
    mouth_center_y = float((left_mouth[1] + right_mouth[1]) / 2.0)
    face_height_hint = mouth_center_y - eye_center_y
    if face_height_hint <= 0:
        return False

    if nose[1] <= eye_center_y or nose[1] >= mouth_center_y:
        return False

    if abs(float(left_eye[1] - right_eye[1])) > eye_distance * 0.45:
        return False

    if abs(float(left_mouth[1] - right_mouth[1])) > mouth_distance * 0.60:
        return False

    mouth_eye_ratio = mouth_distance / eye_distance
    return 0.35 <= mouth_eye_ratio <= 1.80


def map_failure_reason(
    *,
    detection_probability: Optional[float],
    sharpness: float,
    brightness: float,
    face_size_ratio: float,
    landmarks_present: bool,
    landmark_geometry_valid: bool,
    yaw_estimate: Optional[float],
    thresholds: FaceQualityThresholds = DEFAULT_FACE_QUALITY_THRESHOLDS,
) -> Optional[str]:
    if detection_probability is None or detection_probability < thresholds.min_detection_probability:
        return FaceQualityReason.LOW_DETECTION_CONFIDENCE.value
    if sharpness < thresholds.min_sharpness:
        return FaceQualityReason.LOW_SHARPNESS.value
    if brightness < thresholds.min_brightness:
        return FaceQualityReason.LOW_BRIGHTNESS.value
    if brightness > thresholds.max_brightness:
        return FaceQualityReason.HIGH_BRIGHTNESS.value
    if face_size_ratio < thresholds.min_face_size_ratio:
        return FaceQualityReason.FACE_TOO_SMALL.value
    if not landmarks_present:
        return FaceQualityReason.LANDMARK_MISSING.value
    if not landmark_geometry_valid:
        return FaceQualityReason.LANDMARK_GEOMETRY_INVALID.value
    if yaw_estimate is not None and abs(yaw_estimate) > thresholds.max_yaw_ratio:
        return FaceQualityReason.POSE_OUT_OF_RANGE.value
    return None


def evaluate_face_quality(
    image: Image.Image,
    bbox: Sequence[float],
    detection_probability: Optional[float],
    landmarks: Optional[Sequence[Sequence[float]]],
    thresholds: FaceQualityThresholds = DEFAULT_FACE_QUALITY_THRESHOLDS,
) -> FaceQualityResult:
    sharpness = calculate_sharpness(image)
    brightness = calculate_brightness(image)
    face_size_ratio = calculate_face_size_ratio(bbox, image.size)
    yaw_estimate = estimate_yaw_from_landmarks(landmarks)
    landmarks_present = normalize_landmarks(landmarks) is not None
    landmark_geometry_valid = validate_landmark_geometry(landmarks)

    reason_code = map_failure_reason(
        detection_probability=detection_probability,
        sharpness=sharpness,
        brightness=brightness,
        face_size_ratio=face_size_ratio,
        landmarks_present=landmarks_present,
        landmark_geometry_valid=landmark_geometry_valid,
        yaw_estimate=yaw_estimate,
        thresholds=thresholds,
    )
    return FaceQualityResult(
        passed=reason_code is None,
        final_result="PASS" if reason_code is None else "FACE_UNCLEAR",
        reason_code=reason_code,
        metrics=FaceQualityMetrics(
            sharpness=sharpness,
            brightness=brightness,
            face_size_ratio=face_size_ratio,
            yaw_estimate=yaw_estimate,
            landmark_geometry_valid=landmark_geometry_valid,
        ),
    )
