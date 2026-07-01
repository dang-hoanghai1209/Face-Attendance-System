from services.multi_frame_voting_service import (
    MULTI_FRAME_VOTING_CONFIG,
    evaluate_multi_frame_votes,
)


def recognized(student_code="SV001", confidence=0.9, margin=0.1, student_id=None):
    return {
        "status": "RECOGNIZED",
        "student_id": student_id,
        "student_code": student_code,
        "confidence": confidence,
        "margin": margin,
        "quality_passed": True,
        "liveness_passed": True,
    }


def unknown():
    return {
        "status": "FACE_UNKNOWN",
        "quality_passed": True,
        "liveness_passed": True,
    }


def unclear(reason_code="LOW_SHARPNESS"):
    return {
        "status": "FACE_UNCLEAR",
        "reason_code": reason_code,
        "quality_passed": False,
        "liveness_passed": True,
    }


def test_majority_same_student_returns_recognized():
    result = evaluate_multi_frame_votes(
        [
            recognized("SV001", 0.91),
            recognized("SV001", 0.89),
            recognized("SV001", 0.93),
            recognized("SV002", 0.86),
            unknown(),
        ]
    )

    assert result["status"] == "RECOGNIZED"
    assert result["student_code"] == "SV001"
    assert result["vote_count"] == 3
    assert result["required_votes"] == 3
    assert result["total_frames"] == 5
    assert result["valid_frames"] == 5
    assert result["reason_code"] is None
    assert round(result["confidence"], 3) == 0.91


def test_empty_frame_list_returns_uncertain():
    result = evaluate_multi_frame_votes([])

    assert result["status"] == "FACE_UNCERTAIN"
    assert result["reason_code"] == "INSUFFICIENT_VALID_FRAMES"
    assert result["total_frames"] == 0


def test_too_few_valid_frames_returns_uncertain():
    liveness_failed = {"status": "FACE_UNKNOWN", "quality_passed": True, "liveness_passed": False}
    result = evaluate_multi_frame_votes(
        [
            recognized("SV001", 0.91),
            recognized("SV001", 0.90),
            liveness_failed,
            liveness_failed,
            liveness_failed,
        ]
    )

    assert result["status"] == "FACE_UNCERTAIN"
    assert result["reason_code"] == "INSUFFICIENT_VALID_FRAMES"
    assert result["valid_frames"] == 2


def test_mostly_unclear_frames_returns_face_unclear():
    result = evaluate_multi_frame_votes(
        [
            unclear(),
            unclear("LOW_BRIGHTNESS"),
            unclear("FACE_TOO_SMALL"),
            recognized("SV001", 0.9),
            unknown(),
        ]
    )

    assert result["status"] == "FACE_UNCLEAR"
    assert result["reason_code"] == "LOW_FRAME_QUALITY"
    assert result["details"]["unclear_count"] == 3


def test_split_votes_between_students_returns_uncertain():
    result = evaluate_multi_frame_votes(
        [
            recognized("SV001", 0.91),
            recognized("SV001", 0.89),
            recognized("SV002", 0.92),
            recognized("SV002", 0.90),
            unknown(),
        ]
    )

    assert result["status"] == "FACE_UNCERTAIN"
    assert result["reason_code"] == "LOW_VOTE_AGREEMENT"
    assert result["vote_count"] == 2


def test_low_confidence_winner_returns_uncertain():
    result = evaluate_multi_frame_votes(
        [
            recognized("SV001", 0.62),
            recognized("SV001", 0.66),
            recognized("SV001", 0.68),
            unknown(),
            unknown(),
        ]
    )

    assert result["status"] == "FACE_UNCERTAIN"
    assert result["reason_code"] == "LOW_CONFIDENCE"
    assert result["student_code"] == "SV001"


def test_low_margin_returns_uncertain():
    result = evaluate_multi_frame_votes(
        [
            recognized("SV001", 0.91, margin=0.02),
            recognized("SV001", 0.89, margin=0.03),
            recognized("SV001", 0.90, margin=0.04),
            unknown(),
            unknown(),
        ]
    )

    assert result["status"] == "FACE_UNCERTAIN"
    assert result["reason_code"] == "LOW_IDENTITY_MARGIN"
    assert result["student_code"] == "SV001"


def test_unknown_frames_only_returns_face_unknown():
    result = evaluate_multi_frame_votes([unknown(), unknown(), unknown(), unknown(), unknown()])

    assert result["status"] == "FACE_UNKNOWN"
    assert result["reason_code"] == "NO_MATCHING_IDENTITY"


def test_config_override_allows_smaller_batch():
    result = evaluate_multi_frame_votes(
        [recognized("SV001", 0.91), recognized("SV001", 0.90), unknown()],
        config={"min_total_frames": 3, "min_quality_frames": 2, "min_agreement_ratio": 0.6},
    )

    assert result["status"] == "RECOGNIZED"
    assert result["student_code"] == "SV001"
    assert result["required_votes"] == 2


def test_mixed_noisy_frames_still_selects_winner():
    result = evaluate_multi_frame_votes(
        [
            recognized("SV001", 0.91),
            recognized("SV001", 0.88),
            recognized("SV001", 0.94),
            {"status": "FACE_UNCERTAIN", "quality_passed": True, "liveness_passed": True},
            unclear(),
            unknown(),
        ]
    )

    assert result["status"] == "RECOGNIZED"
    assert result["student_code"] == "SV001"
    assert result["vote_count"] == 3
    assert result["valid_frames"] == 5


def test_default_config_contains_required_keys():
    assert {
        "min_total_frames",
        "min_quality_frames",
        "min_agreement_ratio",
        "min_confidence",
        "min_margin",
        "max_unclear_ratio",
    }.issubset(MULTI_FRAME_VOTING_CONFIG)
