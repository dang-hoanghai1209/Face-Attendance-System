from dataclasses import dataclass
from enum import Enum
import os
from typing import Any, Optional, Sequence

import numpy as np
from PIL import Image, ImageFilter, ImageStat


# Calibrated against available repo samples in backend/media/recognition_attempts.
# Real classroom camera samples should still be used before production gating.
DEFAULT_MIN_SHARPNESS = 20.0
DEFAULT_MIN_BRIGHTNESS = 45.0
DEFAULT_MAX_BRIGHTNESS = 220.0
DEFAULT_MIN_FACE_SIZE_RATIO = 0.08
DEFAULT_MIN_DETECTION_PROBABILITY = 0.90
DEFAULT_MAX_YAW_RATIO = 0.35
DEFAULT_MAX_PITCH_RATIO = 0.35
DEFAULT_MAX_ROLL_DEGREES = 15.0

DEFAULT_FACE_QUALITY_CONFIG = {
    "min_sharpness": DEFAULT_MIN_SHARPNESS,
    "min_brightness": DEFAULT_MIN_BRIGHTNESS,
    "max_brightness": DEFAULT_MAX_BRIGHTNESS,
    "min_face_size_ratio": DEFAULT_MIN_FACE_SIZE_RATIO,
    "min_detection_confidence": DEFAULT_MIN_DETECTION_PROBABILITY,
    "max_abs_yaw": DEFAULT_MAX_YAW_RATIO,
    "max_abs_pitch": DEFAULT_MAX_PITCH_RATIO,
    "max_abs_roll": DEFAULT_MAX_ROLL_DEGREES,
}


def validate_face_quality_config(config: Optional[dict[str, Any]] = None) -> dict:
    values = dict(DEFAULT_FACE_QUALITY_CONFIG)
    if config:
        values.update(config)

    errors = []
    _validate_min(values, "min_sharpness", 0.0, errors)
    _validate_range(values, "min_brightness", 0.0, 255.0, errors)
    _validate_range(values, "max_brightness", 0.0, 255.0, errors)
    if _to_number(values.get("min_brightness")) is not None and _to_number(values.get("max_brightness")) is not None:
        if float(values["min_brightness"]) > float(values["max_brightness"]):
            errors.append("min_brightness must be less than or equal to max_brightness")
    _validate_range(values, "min_face_size_ratio", 0.0, 1.0, errors)
    _validate_range(values, "min_detection_confidence", 0.0, 1.0, errors)
    _validate_min(values, "max_abs_yaw", 0.0, errors)
    _validate_min(values, "max_abs_pitch", 0.0, errors)
    _validate_min(values, "max_abs_roll", 0.0, errors)

    return {
        "valid": not errors,
        "errors": errors,
        "config": values,
    }


def _validate_min(values: dict[str, Any], key: str, minimum: float, errors: list[str]) -> None:
    number = _to_number(values.get(key))
    if number is None:
        errors.append(f"{key} must be a number")
    elif number < minimum:
        errors.append(f"{key} must be >= {minimum}")


def _validate_range(values: dict[str, Any], key: str, minimum: float, maximum: float, errors: list[str]) -> None:
    number = _to_number(values.get(key))
    if number is None:
        errors.append(f"{key} must be a number")
    elif number < minimum or number > maximum:
        errors.append(f"{key} must be between {minimum} and {maximum}")


def _to_number(value: Any) -> Optional[float]:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


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
    max_pitch_ratio: float = DEFAULT_MAX_PITCH_RATIO
    max_roll_degrees: float = DEFAULT_MAX_ROLL_DEGREES


@dataclass(frozen=True)
class FaceQualityMetrics:
    sharpness: float
    brightness: float
    face_size_ratio: float
    yaw_estimate: Optional[float]
    pitch_estimate: Optional[float]
    roll_estimate: Optional[float]
    landmark_geometry_valid: bool


METRIC_DESCRIPTIONS = {
    "sharpness": "Variance of edge intensity from a grayscale image. Lower values usually mean blur or weak detail.",
    "brightness": "Mean grayscale pixel value from 0 to 255. Very low is dark; very high can be overexposed.",
    "face_size_ratio": "Detected face bounding-box area divided by full image area.",
    "detection_confidence": "MTCNN face detection probability for the selected face.",
    "yaw_estimate": "Approximate horizontal pose from nose offset relative to eye center and eye distance.",
    "pitch_estimate": "Approximate vertical pose from nose offset relative to eye and mouth centers.",
    "roll_estimate": "Approximate in-plane head tilt in degrees from the eye line.",
    "landmark_geometry": "Neutral sanity checks for five MTCNN landmarks: eye, nose, and mouth ordering/spacing.",
}

FACE_QUALITY_MESSAGES = {
    FaceQualityReason.LOW_SHARPNESS.value: "Face image is not sharp enough.",
    FaceQualityReason.LOW_BRIGHTNESS.value: "Face image is too dark.",
    FaceQualityReason.HIGH_BRIGHTNESS.value: "Face image is too bright.",
    FaceQualityReason.FACE_TOO_SMALL.value: "Detected face is too small.",
    FaceQualityReason.POSE_OUT_OF_RANGE.value: "Face pose is out of range.",
    FaceQualityReason.LANDMARK_MISSING.value: "Face landmarks are missing.",
    FaceQualityReason.LANDMARK_GEOMETRY_INVALID.value: "Face landmark geometry is invalid.",
    FaceQualityReason.LOW_DETECTION_CONFIDENCE.value: "Face detection confidence is too low.",
    FaceQualityReason.LOW_FACE_QUALITY.value: "Face quality is too low.",
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
        max_pitch_ratio=_parse_float_env("FACE_QUALITY_MAX_PITCH_RATIO", DEFAULT_MAX_PITCH_RATIO, minimum=0.0),
        max_roll_degrees=_parse_float_env(
            "FACE_QUALITY_MAX_ROLL_DEGREES",
            DEFAULT_MAX_ROLL_DEGREES,
            minimum=0.0,
        ),
    )


DEFAULT_FACE_QUALITY_THRESHOLDS = FaceQualityThresholds()


def _as_pil_image(image: Any) -> Image.Image:
    if isinstance(image, Image.Image):
        return image
    return Image.fromarray(np.asarray(image))


def _thresholds_from_config(config: Optional[Any]) -> FaceQualityThresholds:
    if config is None:
        return DEFAULT_FACE_QUALITY_THRESHOLDS
    if isinstance(config, FaceQualityThresholds):
        return config
    if isinstance(config, dict):
        return FaceQualityThresholds(
            min_sharpness=float(config.get("min_sharpness", DEFAULT_MIN_SHARPNESS)),
            min_brightness=float(config.get("min_brightness", DEFAULT_MIN_BRIGHTNESS)),
            max_brightness=float(config.get("max_brightness", DEFAULT_MAX_BRIGHTNESS)),
            min_face_size_ratio=float(config.get("min_face_size_ratio", DEFAULT_MIN_FACE_SIZE_RATIO)),
            min_detection_probability=float(
                config.get(
                    "min_detection_confidence",
                    config.get("min_detection_probability", DEFAULT_MIN_DETECTION_PROBABILITY),
                )
            ),
            max_yaw_ratio=float(config.get("max_abs_yaw", config.get("max_yaw_ratio", DEFAULT_MAX_YAW_RATIO))),
            max_pitch_ratio=float(
                config.get("max_abs_pitch", config.get("max_pitch_ratio", DEFAULT_MAX_PITCH_RATIO))
            ),
            max_roll_degrees=float(
                config.get("max_abs_roll", config.get("max_roll_degrees", DEFAULT_MAX_ROLL_DEGREES))
            ),
        )
    return DEFAULT_FACE_QUALITY_THRESHOLDS


def calculate_sharpness(image: Image.Image) -> float:
    """Return edge-variance sharpness; low values are useful for blur calibration."""
    grayscale = _as_pil_image(image).convert("L")
    edges = grayscale.filter(ImageFilter.FIND_EDGES)
    values = np.asarray(edges, dtype=np.float32)
    return round(float(values.var()), 4)


def calculate_brightness(image: Image.Image) -> float:
    """Return mean grayscale brightness on the 0-255 pixel scale."""
    grayscale = _as_pil_image(image).convert("L")
    return round(float(ImageStat.Stat(grayscale).mean[0]), 4)


def calculate_face_size_ratio(bbox: Sequence[float], image_shape: Sequence[int]) -> float:
    """Return detected face area divided by image area."""
    if len(image_shape) >= 3:
        image_height, image_width = int(image_shape[0]), int(image_shape[1])
    else:
        image_width, image_height = int(image_shape[0]), int(image_shape[1])
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


def estimate_pose_from_landmarks(landmarks: Optional[Sequence[Sequence[float]]]) -> dict:
    points = normalize_landmarks(landmarks)
    if points is None:
        return {"yaw": None, "pitch": None, "roll": None}

    left_eye, right_eye, nose, left_mouth, right_mouth = points
    eye_distance = float(np.linalg.norm(right_eye - left_eye))
    if eye_distance <= 0:
        return {"yaw": None, "pitch": None, "roll": None}

    eye_center = (left_eye + right_eye) / 2.0
    mouth_center = (left_mouth + right_mouth) / 2.0
    eye_to_mouth = float(mouth_center[1] - eye_center[1])
    yaw = float((nose[0] - eye_center[0]) / eye_distance)
    roll = float(np.degrees(np.arctan2(right_eye[1] - left_eye[1], right_eye[0] - left_eye[0])))
    pitch = None
    if eye_to_mouth > 0:
        expected_nose_y = float((eye_center[1] + mouth_center[1]) / 2.0)
        pitch = float((nose[1] - expected_nose_y) / eye_to_mouth)

    return {
        "yaw": round(yaw, 4),
        "pitch": round(pitch, 4) if pitch is not None else None,
        "roll": round(roll, 4),
    }


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


def validate_landmarks(landmarks: Optional[Sequence[Sequence[float]]], bbox=None) -> dict:
    points = normalize_landmarks(landmarks)
    if points is None:
        return {
            "valid": False,
            "reason_code": FaceQualityReason.LANDMARK_MISSING.value,
            "message": "Face landmarks are missing or malformed.",
        }

    geometry_valid = validate_landmark_geometry(points)
    if not geometry_valid:
        return {
            "valid": False,
            "reason_code": FaceQualityReason.LANDMARK_GEOMETRY_INVALID.value,
            "message": "Face landmark geometry is invalid.",
        }

    if bbox is not None:
        x1, y1, x2, y2 = [float(value) for value in bbox]
        in_bbox = (
            np.all(points[:, 0] >= x1)
            and np.all(points[:, 0] <= x2)
            and np.all(points[:, 1] >= y1)
            and np.all(points[:, 1] <= y2)
        )
        if not in_bbox:
            return {
                "valid": False,
                "reason_code": FaceQualityReason.LANDMARK_GEOMETRY_INVALID.value,
                "message": "Face landmarks are outside the bounding box.",
            }

    return {"valid": True, "reason_code": None, "message": "Face landmarks are valid."}


def map_failure_reason(
    *,
    detection_probability: Optional[float],
    sharpness: float,
    brightness: float,
    face_size_ratio: float,
    landmarks_present: bool,
    landmark_geometry_valid: bool,
    yaw_estimate: Optional[float],
    pitch_estimate: Optional[float] = None,
    roll_estimate: Optional[float] = None,
    thresholds: FaceQualityThresholds = DEFAULT_FACE_QUALITY_THRESHOLDS,
) -> Optional[str]:
    failed_checks = collect_failed_checks(
        detection_probability=detection_probability,
        sharpness=sharpness,
        brightness=brightness,
        face_size_ratio=face_size_ratio,
        landmarks_present=landmarks_present,
        landmark_geometry_valid=landmark_geometry_valid,
        yaw_estimate=yaw_estimate,
        pitch_estimate=pitch_estimate,
        roll_estimate=roll_estimate,
        thresholds=thresholds,
    )
    return failed_checks[0] if failed_checks else None


def collect_failed_checks(
    *,
    detection_probability: Optional[float],
    sharpness: float,
    brightness: float,
    face_size_ratio: float,
    landmarks_present: bool,
    landmark_geometry_valid: bool,
    yaw_estimate: Optional[float],
    pitch_estimate: Optional[float] = None,
    roll_estimate: Optional[float] = None,
    thresholds: FaceQualityThresholds = DEFAULT_FACE_QUALITY_THRESHOLDS,
) -> list[str]:
    failed_checks = []
    if detection_probability is None or detection_probability < thresholds.min_detection_probability:
        failed_checks.append(FaceQualityReason.LOW_DETECTION_CONFIDENCE.value)
    if sharpness < thresholds.min_sharpness:
        failed_checks.append(FaceQualityReason.LOW_SHARPNESS.value)
    if brightness < thresholds.min_brightness:
        failed_checks.append(FaceQualityReason.LOW_BRIGHTNESS.value)
    if brightness > thresholds.max_brightness:
        failed_checks.append(FaceQualityReason.HIGH_BRIGHTNESS.value)
    if face_size_ratio < thresholds.min_face_size_ratio:
        failed_checks.append(FaceQualityReason.FACE_TOO_SMALL.value)
    if not landmarks_present:
        failed_checks.append(FaceQualityReason.LANDMARK_MISSING.value)
    if landmarks_present and not landmark_geometry_valid:
        failed_checks.append(FaceQualityReason.LANDMARK_GEOMETRY_INVALID.value)
    pose_out_of_range = (
        (yaw_estimate is not None and abs(yaw_estimate) > thresholds.max_yaw_ratio)
        or (pitch_estimate is not None and abs(pitch_estimate) > thresholds.max_pitch_ratio)
        or (roll_estimate is not None and abs(roll_estimate) > thresholds.max_roll_degrees)
    )
    if pose_out_of_range:
        failed_checks.append(FaceQualityReason.POSE_OUT_OF_RANGE.value)
    return failed_checks


def _evaluate_face_quality_result(
    image: Image.Image,
    bbox: Sequence[float],
    detection_probability: Optional[float],
    landmarks: Optional[Sequence[Sequence[float]]],
    thresholds: FaceQualityThresholds = DEFAULT_FACE_QUALITY_THRESHOLDS,
) -> FaceQualityResult:
    sharpness = calculate_sharpness(image)
    brightness = calculate_brightness(image)
    face_size_ratio = calculate_face_size_ratio(bbox, image.size)
    pose = estimate_pose_from_landmarks(landmarks)
    yaw_estimate = pose["yaw"]
    pitch_estimate = pose["pitch"]
    roll_estimate = pose["roll"]
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
        pitch_estimate=pitch_estimate,
        roll_estimate=roll_estimate,
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
            pitch_estimate=pitch_estimate,
            roll_estimate=roll_estimate,
            landmark_geometry_valid=landmark_geometry_valid,
        ),
    )


def _get_face_result_value(face_result: Any, *names: str):
    for name in names:
        if isinstance(face_result, dict) and name in face_result:
            return face_result[name]
        if hasattr(face_result, name):
            return getattr(face_result, name)
    return None


def _quality_message(reason_code: Optional[str]) -> str:
    if reason_code is None:
        return "Face quality passed."
    return FACE_QUALITY_MESSAGES.get(reason_code, FACE_QUALITY_MESSAGES[FaceQualityReason.LOW_FACE_QUALITY.value])


def evaluate_face_quality(
    image: Image.Image,
    face_result: Any = None,
    config: Optional[Any] = None,
    *legacy_args,
    **legacy_kwargs,
) -> dict:
    """Evaluate one detected face and return a stable dict for debug tooling.

    Preferred call shape is evaluate_face_quality(image, face_result, config=None)
    where face_result contains bbox/box, landmarks, and confidence/probability.
    The older positional shape is still accepted for compatibility:
    evaluate_face_quality(image, bbox, detection_probability, landmarks, thresholds=...).
    """
    if legacy_args or "thresholds" in legacy_kwargs:
        bbox = face_result
        detection_confidence = config
        landmarks = legacy_args[0] if len(legacy_args) > 0 else None
        thresholds = legacy_kwargs.get("thresholds", None)
    else:
        bbox = _get_face_result_value(face_result, "bbox", "box", "boxes")
        detection_confidence = _get_face_result_value(
            face_result,
            "detection_confidence",
            "confidence",
            "probability",
            "prob",
        )
        landmarks = _get_face_result_value(face_result, "landmarks", "points")
        thresholds = config

    thresholds = _thresholds_from_config(thresholds)
    pil_image = _as_pil_image(image).convert("RGB")
    sharpness = calculate_sharpness(pil_image)
    brightness = calculate_brightness(pil_image)
    face_size_ratio = calculate_face_size_ratio(bbox, pil_image.size) if bbox is not None else 0.0
    landmark_result = validate_landmarks(landmarks, bbox=bbox)
    pose = estimate_pose_from_landmarks(landmarks)
    failed_checks = collect_failed_checks(
        detection_probability=detection_confidence,
        sharpness=sharpness,
        brightness=brightness,
        face_size_ratio=face_size_ratio,
        landmarks_present=normalize_landmarks(landmarks) is not None,
        landmark_geometry_valid=bool(landmark_result["valid"]),
        yaw_estimate=pose["yaw"],
        pitch_estimate=pose["pitch"],
        roll_estimate=pose["roll"],
        thresholds=thresholds,
    )

    reason_code = failed_checks[0] if failed_checks else None

    if reason_code is None and bbox is None:
        reason_code = FaceQualityReason.LOW_FACE_QUALITY.value
        failed_checks = [reason_code]

    return {
        "passed": reason_code is None,
        "status": "PASS" if reason_code is None else "FACE_UNCLEAR",
        "reason_code": reason_code,
        "message": _quality_message(reason_code),
        "details": {
            "sharpness": sharpness,
            "brightness": brightness,
            "face_size_ratio": face_size_ratio,
            "detection_confidence": None if detection_confidence is None else round(float(detection_confidence), 4),
            "pose": pose,
            "landmark_valid": bool(landmark_result["valid"]),
            "failed_checks": failed_checks,
        },
    }


def evaluate_face_quality_result(
    image: Image.Image,
    bbox: Sequence[float],
    detection_probability: Optional[float],
    landmarks: Optional[Sequence[Sequence[float]]],
    thresholds: FaceQualityThresholds = DEFAULT_FACE_QUALITY_THRESHOLDS,
) -> FaceQualityResult:
    return _evaluate_face_quality_result(image, bbox, detection_probability, landmarks, thresholds)


def face_quality_config_from_env() -> dict:
    thresholds = load_face_quality_thresholds_from_env()
    return {
        "min_sharpness": thresholds.min_sharpness,
        "min_brightness": thresholds.min_brightness,
        "max_brightness": thresholds.max_brightness,
        "min_face_size_ratio": thresholds.min_face_size_ratio,
        "max_abs_yaw": thresholds.max_yaw_ratio,
        "max_abs_pitch": thresholds.max_pitch_ratio,
        "max_abs_roll": thresholds.max_roll_degrees,
        "min_detection_confidence": thresholds.min_detection_probability,
    }
