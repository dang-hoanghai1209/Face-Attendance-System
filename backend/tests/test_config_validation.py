import pytest

from services.face_quality_service import DEFAULT_FACE_QUALITY_CONFIG, validate_face_quality_config
from services.multi_frame_voting_service import (
    MULTI_FRAME_VOTING_CONFIG,
    evaluate_multi_frame_votes,
    validate_multi_frame_voting_config,
)


def test_valid_default_configs_pass_validation():
    assert validate_face_quality_config(DEFAULT_FACE_QUALITY_CONFIG)["valid"] is True
    assert validate_multi_frame_voting_config(MULTI_FRAME_VOTING_CONFIG)["valid"] is True


def test_invalid_face_quality_brightness_range_fails():
    result = validate_face_quality_config({"min_brightness": 240.0, "max_brightness": 120.0})

    assert result["valid"] is False
    assert "min_brightness must be less than or equal to max_brightness" in result["errors"]


def test_invalid_face_quality_confidence_fails():
    result = validate_face_quality_config({"min_detection_confidence": 1.2})

    assert result["valid"] is False
    assert "min_detection_confidence must be between 0.0 and 1.0" in result["errors"]


def test_invalid_multi_frame_ratio_fails():
    result = validate_multi_frame_voting_config({"min_agreement_ratio": 1.5})

    assert result["valid"] is False
    assert "min_agreement_ratio must be between 0.0 and 1.0" in result["errors"]


def test_invalid_multi_frame_min_frames_fails():
    result = validate_multi_frame_voting_config({"min_total_frames": 2, "min_quality_frames": 3})

    assert result["valid"] is False
    assert "min_quality_frames must be less than or equal to min_total_frames" in result["errors"]


def test_evaluate_multi_frame_votes_rejects_invalid_config():
    with pytest.raises(ValueError, match="min_confidence"):
        evaluate_multi_frame_votes([], config={"min_confidence": -0.1})
