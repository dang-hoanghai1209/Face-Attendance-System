from __future__ import annotations

from collections import Counter, defaultdict
from math import ceil
from typing import Any, Optional


MULTI_FRAME_VOTING_CONFIG = {
    "min_total_frames": 5,
    "min_quality_frames": 3,
    "min_agreement_ratio": 0.6,
    "min_confidence": 0.70,
    "min_margin": 0.05,
    "max_unclear_ratio": 0.5,
}


MULTI_FRAME_REASON_CODES = {
    "INSUFFICIENT_VALID_FRAMES": "INSUFFICIENT_VALID_FRAMES",
    "LOW_FRAME_QUALITY": "LOW_FRAME_QUALITY",
    "LOW_VOTE_AGREEMENT": "LOW_VOTE_AGREEMENT",
    "LOW_CONFIDENCE": "LOW_CONFIDENCE",
    "LOW_IDENTITY_MARGIN": "LOW_IDENTITY_MARGIN",
    "UNSTABLE_IDENTITY": "UNSTABLE_IDENTITY",
    "NO_MATCHING_IDENTITY": "NO_MATCHING_IDENTITY",
}


STATUS_RECOGNIZED = "RECOGNIZED"
STATUS_UNCERTAIN = "FACE_UNCERTAIN"
STATUS_UNCLEAR = "FACE_UNCLEAR"
STATUS_UNKNOWN = "FACE_UNKNOWN"


def evaluate_multi_frame_votes(frame_results: list[dict[str, Any]], config: Optional[dict[str, Any]] = None) -> dict[str, Any]:
    """Evaluate identity stability across per-frame recognition results.

    This service deliberately accepts plain dictionaries so route code can feed
    it existing recognition outputs without coupling it to model inference.
    """

    thresholds = _merge_config(config)
    frames = [_normalize_frame(frame) for frame in frame_results or []]
    total_frames = len(frames)

    base_details = {
        "config": thresholds,
        "status_counts": dict(Counter(frame["status"] for frame in frames)),
        "identity_votes": {},
    }

    if total_frames < thresholds["min_total_frames"]:
        return _build_result(
            STATUS_UNCERTAIN,
            total_frames=total_frames,
            valid_frames=0,
            required_votes=thresholds["min_quality_frames"],
            reason_code=MULTI_FRAME_REASON_CODES["INSUFFICIENT_VALID_FRAMES"],
            details=base_details,
        )

    unclear_count = sum(1 for frame in frames if _is_unclear_frame(frame))
    unclear_ratio = unclear_count / total_frames if total_frames else 0.0
    if unclear_ratio > thresholds["max_unclear_ratio"]:
        details = {**base_details, "unclear_count": unclear_count, "unclear_ratio": unclear_ratio}
        return _build_result(
            STATUS_UNCLEAR,
            total_frames=total_frames,
            valid_frames=total_frames - unclear_count,
            required_votes=thresholds["min_quality_frames"],
            reason_code=MULTI_FRAME_REASON_CODES["LOW_FRAME_QUALITY"],
            details=details,
        )

    valid_frames = [frame for frame in frames if _is_valid_quality_frame(frame)]
    valid_count = len(valid_frames)
    if valid_count < thresholds["min_quality_frames"]:
        details = {**base_details, "valid_frame_count": valid_count, "unclear_count": unclear_count}
        return _build_result(
            STATUS_UNCERTAIN,
            total_frames=total_frames,
            valid_frames=valid_count,
            required_votes=thresholds["min_quality_frames"],
            reason_code=MULTI_FRAME_REASON_CODES["INSUFFICIENT_VALID_FRAMES"],
            details=details,
        )

    identity_frames = [frame for frame in valid_frames if frame["status"] == STATUS_RECOGNIZED and frame["identity_key"]]
    if not identity_frames:
        unknown_count = sum(1 for frame in valid_frames if frame["status"] == STATUS_UNKNOWN)
        status = STATUS_UNKNOWN if unknown_count else STATUS_UNCERTAIN
        details = {**base_details, "valid_frame_count": valid_count, "unknown_count": unknown_count}
        return _build_result(
            status,
            total_frames=total_frames,
            valid_frames=valid_count,
            required_votes=thresholds["min_quality_frames"],
            reason_code=MULTI_FRAME_REASON_CODES["NO_MATCHING_IDENTITY"],
            details=details,
        )

    grouped = _group_identity_frames(identity_frames)
    identity_votes = {
        key: {
            "vote_count": len(group_frames),
            "average_confidence": _average([frame["confidence"] for frame in group_frames]),
            "student_id": _first_value(group_frames, "student_id"),
            "student_code": _first_value(group_frames, "student_code"),
        }
        for key, group_frames in grouped.items()
    }
    winner_key, winner_frames = max(grouped.items(), key=lambda item: (len(item[1]), _average([f["confidence"] for f in item[1]])))
    winner_vote_count = len(winner_frames)
    required_votes = max(thresholds["min_quality_frames"], ceil(thresholds["min_agreement_ratio"] * valid_count))
    agreement_ratio = winner_vote_count / valid_count if valid_count else 0.0

    details = {
        **base_details,
        "identity_votes": identity_votes,
        "winner_key": winner_key,
        "valid_frame_count": valid_count,
    }

    if agreement_ratio < thresholds["min_agreement_ratio"] or winner_vote_count < required_votes:
        return _build_result(
            STATUS_UNCERTAIN,
            vote_count=winner_vote_count,
            required_votes=required_votes,
            total_frames=total_frames,
            valid_frames=valid_count,
            agreement_ratio=agreement_ratio,
            reason_code=MULTI_FRAME_REASON_CODES["LOW_VOTE_AGREEMENT"],
            details=details,
        )

    winner_confidence = _average([frame["confidence"] for frame in winner_frames])
    if winner_confidence < thresholds["min_confidence"]:
        return _build_result(
            STATUS_UNCERTAIN,
            student_id=_first_value(winner_frames, "student_id"),
            student_code=_first_value(winner_frames, "student_code"),
            confidence=winner_confidence,
            vote_count=winner_vote_count,
            required_votes=required_votes,
            total_frames=total_frames,
            valid_frames=valid_count,
            agreement_ratio=agreement_ratio,
            reason_code=MULTI_FRAME_REASON_CODES["LOW_CONFIDENCE"],
            details=details,
        )

    winner_margin = _winner_margin(winner_key, winner_frames, grouped)
    details["winner_margin"] = winner_margin
    if winner_margin is not None and winner_margin < thresholds["min_margin"]:
        return _build_result(
            STATUS_UNCERTAIN,
            student_id=_first_value(winner_frames, "student_id"),
            student_code=_first_value(winner_frames, "student_code"),
            confidence=winner_confidence,
            vote_count=winner_vote_count,
            required_votes=required_votes,
            total_frames=total_frames,
            valid_frames=valid_count,
            agreement_ratio=agreement_ratio,
            reason_code=MULTI_FRAME_REASON_CODES["LOW_IDENTITY_MARGIN"],
            details=details,
        )

    return _build_result(
        STATUS_RECOGNIZED,
        student_id=_first_value(winner_frames, "student_id"),
        student_code=_first_value(winner_frames, "student_code"),
        confidence=winner_confidence,
        vote_count=winner_vote_count,
        required_votes=required_votes,
        total_frames=total_frames,
        valid_frames=valid_count,
        agreement_ratio=agreement_ratio,
        reason_code=None,
        details=details,
    )


def _merge_config(config: Optional[dict[str, Any]]) -> dict[str, Any]:
    thresholds = dict(MULTI_FRAME_VOTING_CONFIG)
    if config:
        thresholds.update(config)
    return thresholds


def _normalize_frame(frame: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(frame or {})
    normalized["status"] = _normalize_status(normalized.get("status"))
    normalized["confidence"] = _to_float(normalized.get("confidence", normalized.get("similarity")), default=0.0)
    normalized["margin"] = _to_float(normalized.get("margin"), default=None)
    normalized["student_id"] = normalized.get("student_id")
    normalized["student_code"] = normalized.get("student_code")
    normalized["identity_key"] = normalized.get("student_id") or normalized.get("student_code") or normalized.get("top1_id")
    return normalized


def _normalize_status(status: Any) -> str:
    value = str(status or "").upper()
    if value in {"RECOGNIZED", "SUCCESS", "MATCHED"}:
        return STATUS_RECOGNIZED
    if value in {"FACE_UNCLEAR", "UNCLEAR"}:
        return STATUS_UNCLEAR
    if value in {"FACE_UNKNOWN", "UNKNOWN", "NO_FACE"}:
        return STATUS_UNKNOWN
    return STATUS_UNCERTAIN


def _is_unclear_frame(frame: dict[str, Any]) -> bool:
    return frame["status"] == STATUS_UNCLEAR or frame.get("quality_passed") is False


def _is_valid_quality_frame(frame: dict[str, Any]) -> bool:
    if _is_unclear_frame(frame):
        return False
    if frame.get("liveness_passed") is False:
        return False
    return True


def _group_identity_frames(frames: list[dict[str, Any]]) -> dict[Any, list[dict[str, Any]]]:
    grouped: dict[Any, list[dict[str, Any]]] = defaultdict(list)
    for frame in frames:
        grouped[frame["identity_key"]].append(frame)
    return dict(grouped)


def _winner_margin(
    winner_key: Any,
    winner_frames: list[dict[str, Any]],
    grouped: dict[Any, list[dict[str, Any]]],
) -> Optional[float]:
    explicit_margins = [frame["margin"] for frame in winner_frames if frame["margin"] is not None]
    if explicit_margins:
        return _average(explicit_margins)

    runner_up_confidences = [
        _average([frame["confidence"] for frame in group_frames])
        for key, group_frames in grouped.items()
        if key != winner_key
    ]
    if not runner_up_confidences:
        return None
    return _average([frame["confidence"] for frame in winner_frames]) - max(runner_up_confidences)


def _build_result(
    status: str,
    *,
    student_id: Any = None,
    student_code: Any = None,
    confidence: Optional[float] = None,
    vote_count: int = 0,
    required_votes: int = 0,
    total_frames: int = 0,
    valid_frames: int = 0,
    agreement_ratio: float = 0.0,
    reason_code: Optional[str],
    details: dict[str, Any],
) -> dict[str, Any]:
    return {
        "status": status,
        "student_id": student_id,
        "student_code": student_code,
        "confidence": confidence,
        "vote_count": vote_count,
        "required_votes": required_votes,
        "total_frames": total_frames,
        "valid_frames": valid_frames,
        "agreement_ratio": agreement_ratio,
        "reason_code": reason_code,
        "details": details,
    }


def _average(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _first_value(frames: list[dict[str, Any]], key: str) -> Any:
    for frame in frames:
        value = frame.get(key)
        if value is not None:
            return value
    return None


def _to_float(value: Any, default: Optional[float]) -> Optional[float]:
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default
