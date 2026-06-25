from PIL import Image, ImageFilter

from services.face_quality_service import (
    FaceQualityReason,
    FaceQualityThresholds,
    calculate_brightness,
    calculate_face_size_ratio,
    calculate_sharpness,
    estimate_yaw_from_landmarks,
    map_failure_reason,
    validate_landmark_geometry,
)


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
