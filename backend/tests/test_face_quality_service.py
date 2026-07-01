from PIL import Image, ImageFilter

from services.face_quality_service import (
    DEFAULT_FACE_QUALITY_CONFIG,
    FACE_QUALITY_MESSAGES,
    FaceQualityReason,
    FaceQualityThresholds,
    METRIC_DESCRIPTIONS,
    calculate_brightness,
    calculate_face_size_ratio,
    calculate_sharpness,
    evaluate_face_quality,
    estimate_pose_from_landmarks,
    estimate_yaw_from_landmarks,
    face_quality_config_from_env,
    load_face_quality_thresholds_from_env,
    map_failure_reason,
    validate_landmarks,
    validate_landmark_geometry,
)


VALID_FACE_RESULT = {
    "bbox": [20, 20, 80, 80],
    "confidence": 0.99,
    "landmarks": [
        [35, 35],
        [65, 35],
        [50, 50],
        [38, 70],
        [62, 70],
    ],
}

LENIENT_TEST_CONFIG = {
    "min_sharpness": 0,
    "min_brightness": 0,
    "max_brightness": 255,
    "min_face_size_ratio": 0.01,
    "min_detection_confidence": 0.9,
    "max_abs_yaw": 1.0,
    "max_abs_pitch": 1.0,
    "max_abs_roll": 90.0,
}


def test_calculate_brightness_uses_grayscale_mean():
    image = Image.new("RGB", (10, 10), (100, 100, 100))

    assert calculate_brightness(image) == 100.0


def test_calculate_sharpness_is_higher_for_edged_image_than_blurred_image():
    image = Image.new("L", (40, 40), 0)
    for x in range(20, 40):
        for y in range(40):
            image.putpixel((x, y), 255)
    edged = image.convert("RGB")
    blurred = edged.filter(ImageFilter.GaussianBlur(radius=4))

    assert calculate_sharpness(edged) > calculate_sharpness(blurred)


def test_calculate_face_size_ratio_uses_bbox_area_over_image_area():
    ratio = calculate_face_size_ratio([10, 20, 30, 60], (100, 100))

    assert ratio == 0.08


def test_validate_landmark_geometry_accepts_normal_five_point_layout():
    landmarks = [
        [30, 30],
        [70, 30],
        [50, 50],
        [35, 75],
        [65, 75],
    ]

    assert validate_landmark_geometry(landmarks) is True
    assert estimate_yaw_from_landmarks(landmarks) == 0.0


def test_validate_landmark_geometry_rejects_invalid_ordering():
    landmarks = [
        [30, 60],
        [70, 60],
        [50, 40],
        [35, 75],
        [65, 75],
    ]

    assert validate_landmark_geometry(landmarks) is False


def test_validate_landmarks_returns_missing_reason():
    result = validate_landmarks(None)

    assert result["valid"] is False
    assert result["reason_code"] == FaceQualityReason.LANDMARK_MISSING.value


def test_validate_landmarks_returns_geometry_invalid_reason():
    landmarks = [
        [30, 60],
        [70, 60],
        [50, 40],
        [35, 75],
        [65, 75],
    ]

    result = validate_landmarks(landmarks)

    assert result["valid"] is False
    assert result["reason_code"] == FaceQualityReason.LANDMARK_GEOMETRY_INVALID.value


def test_estimate_pose_from_landmarks_returns_yaw_and_pitch():
    landmarks = [
        [30, 30],
        [70, 30],
        [50, 50],
        [35, 75],
        [65, 75],
    ]

    pose = estimate_pose_from_landmarks(landmarks)

    assert pose["yaw"] == 0.0
    assert pose["pitch"] is not None
    assert pose["roll"] == 0.0


def test_reason_code_mapping_prioritizes_low_detection_confidence():
    reason = map_failure_reason(
        detection_probability=0.5,
        sharpness=100,
        brightness=100,
        face_size_ratio=0.4,
        landmarks_present=True,
        landmark_geometry_valid=True,
        yaw_estimate=0.0,
    )

    assert reason == FaceQualityReason.LOW_DETECTION_CONFIDENCE.value


def test_evaluate_face_quality_fails_low_detection_confidence_with_mock_face_result():
    image = Image.new("RGB", (100, 100), (100, 100, 100))
    face_result = {**VALID_FACE_RESULT, "confidence": 0.5}

    result = evaluate_face_quality(
        image,
        face_result,
        config=LENIENT_TEST_CONFIG,
    )

    assert result["passed"] is False
    assert result["status"] == "FACE_UNCLEAR"
    assert result["reason_code"] == FaceQualityReason.LOW_DETECTION_CONFIDENCE.value
    assert result["details"]["detection_confidence"] == 0.5
    assert FaceQualityReason.LOW_DETECTION_CONFIDENCE.value in result["details"]["failed_checks"]


def test_evaluate_face_quality_passes_with_mock_face_result():
    image = Image.new("RGB", (100, 100), (100, 100, 100))

    result = evaluate_face_quality(
        image,
        VALID_FACE_RESULT,
        config=LENIENT_TEST_CONFIG,
    )

    assert result["passed"] is True
    assert result["status"] == "PASS"
    assert result["reason_code"] is None
    assert result["details"]["landmark_valid"] is True
    assert result["details"]["failed_checks"] == []


def test_default_face_quality_config_contains_calibration_keys():
    expected_keys = {
        "min_sharpness",
        "min_brightness",
        "max_brightness",
        "min_face_size_ratio",
        "max_abs_yaw",
        "max_abs_pitch",
        "max_abs_roll",
        "min_detection_confidence",
    }

    assert expected_keys.issubset(DEFAULT_FACE_QUALITY_CONFIG)


def test_face_quality_config_from_env_uses_public_config_keys():
    config = face_quality_config_from_env()

    assert set(DEFAULT_FACE_QUALITY_CONFIG).issubset(config)
    assert "min_detection_probability" not in config
    assert "max_yaw_ratio" not in config


def test_evaluate_face_quality_fails_low_brightness():
    image = Image.new("RGB", (100, 100), (10, 10, 10))
    config = {**LENIENT_TEST_CONFIG, "min_brightness": 45}

    result = evaluate_face_quality(image, VALID_FACE_RESULT, config=config)

    assert result["reason_code"] == FaceQualityReason.LOW_BRIGHTNESS.value


def test_evaluate_face_quality_fails_high_brightness():
    image = Image.new("RGB", (100, 100), (250, 250, 250))
    config = {**LENIENT_TEST_CONFIG, "max_brightness": 220}

    result = evaluate_face_quality(image, VALID_FACE_RESULT, config=config)

    assert result["reason_code"] == FaceQualityReason.HIGH_BRIGHTNESS.value


def test_evaluate_face_quality_fails_low_sharpness():
    image = Image.new("RGB", (100, 100), (100, 100, 100))
    config = {**LENIENT_TEST_CONFIG, "min_sharpness": 10000}

    result = evaluate_face_quality(image, VALID_FACE_RESULT, config=config)

    assert result["reason_code"] == FaceQualityReason.LOW_SHARPNESS.value


def test_evaluate_face_quality_fails_small_face_ratio():
    image = Image.new("RGB", (100, 100), (100, 100, 100))
    face_result = {**VALID_FACE_RESULT, "bbox": [45, 45, 55, 55]}
    config = {**LENIENT_TEST_CONFIG, "min_face_size_ratio": 0.08}

    result = evaluate_face_quality(image, face_result, config=config)

    assert result["reason_code"] == FaceQualityReason.FACE_TOO_SMALL.value


def test_evaluate_face_quality_fails_landmark_missing():
    image = Image.new("RGB", (100, 100), (100, 100, 100))
    face_result = {**VALID_FACE_RESULT, "landmarks": None}

    result = evaluate_face_quality(image, face_result, config=LENIENT_TEST_CONFIG)

    assert result["reason_code"] == FaceQualityReason.LANDMARK_MISSING.value


def test_reason_code_mapping_returns_landmark_geometry_invalid():
    reason = map_failure_reason(
        detection_probability=0.99,
        sharpness=100,
        brightness=100,
        face_size_ratio=0.4,
        landmarks_present=True,
        landmark_geometry_valid=False,
        yaw_estimate=0.0,
    )

    assert reason == FaceQualityReason.LANDMARK_GEOMETRY_INVALID.value


def test_reason_code_mapping_returns_pose_out_of_range():
    reason = map_failure_reason(
        detection_probability=0.99,
        sharpness=100,
        brightness=100,
        face_size_ratio=0.4,
        landmarks_present=True,
        landmark_geometry_valid=True,
        yaw_estimate=0.5,
        thresholds=FaceQualityThresholds(max_yaw_ratio=0.35),
    )

    assert reason == FaceQualityReason.POSE_OUT_OF_RANGE.value


def test_reason_code_mapping_returns_none_when_quality_passes():
    reason = map_failure_reason(
        detection_probability=0.99,
        sharpness=100,
        brightness=100,
        face_size_ratio=0.4,
        landmarks_present=True,
        landmark_geometry_valid=True,
        yaw_estimate=0.0,
    )

    assert reason is None


def test_load_face_quality_thresholds_from_env_allows_calibration_overrides(monkeypatch):
    monkeypatch.setenv("FACE_QUALITY_MIN_SHARPNESS", "12.5")
    monkeypatch.setenv("FACE_QUALITY_MIN_BRIGHTNESS", "50")
    monkeypatch.setenv("FACE_QUALITY_MAX_BRIGHTNESS", "210")
    monkeypatch.setenv("FACE_QUALITY_MIN_FACE_SIZE_RATIO", "0.12")
    monkeypatch.setenv("FACE_QUALITY_MIN_DETECTION_PROBABILITY", "0.95")
    monkeypatch.setenv("FACE_QUALITY_MAX_YAW_RATIO", "0.25")
    monkeypatch.setenv("FACE_QUALITY_MAX_PITCH_RATIO", "0.30")
    monkeypatch.setenv("FACE_QUALITY_MAX_ROLL_DEGREES", "12")

    thresholds = load_face_quality_thresholds_from_env()

    assert thresholds == FaceQualityThresholds(
        min_sharpness=12.5,
        min_brightness=50,
        max_brightness=210,
        min_face_size_ratio=0.12,
        min_detection_probability=0.95,
        max_yaw_ratio=0.25,
        max_pitch_ratio=0.30,
        max_roll_degrees=12,
    )


def test_metric_descriptions_include_calibration_fields():
    assert "sharpness" in METRIC_DESCRIPTIONS
    assert "brightness" in METRIC_DESCRIPTIONS
    assert "face_size_ratio" in METRIC_DESCRIPTIONS
    assert "detection_confidence" in METRIC_DESCRIPTIONS
    assert "yaw_estimate" in METRIC_DESCRIPTIONS
    assert "pitch_estimate" in METRIC_DESCRIPTIONS
    assert "roll_estimate" in METRIC_DESCRIPTIONS
    assert "landmark_geometry" in METRIC_DESCRIPTIONS


def test_face_quality_messages_cover_supported_reason_codes():
    for reason in FaceQualityReason:
        assert reason.value in FACE_QUALITY_MESSAGES
