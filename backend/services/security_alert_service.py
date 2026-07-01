import json
from pathlib import Path
import shutil
from uuid import uuid4

from models.security_alert import SecurityAlert
from services.timezone_service import now_in_app_timezone


BASE_DIR = Path(__file__).resolve().parents[1]
ALERT_TYPES = {"SPOOF", "UNKNOWN_FACE", "NOT_ENROLLED", "LATE_ENTRY", "FACE_UNCLEAR"}


def save_alert_capture(session_id: int, image_bytes: bytes | None):
    if not image_bytes:
        return None

    now = now_in_app_timezone()
    relative_dir = Path("media") / "alerts" / str(session_id)
    output_dir = BASE_DIR / relative_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{uuid4().hex}.jpg"
    output_path = output_dir / filename
    output_path.write_bytes(image_bytes)
    return str(relative_dir / filename).replace("\\", "/")


def save_face_unclear_snapshot(session_id: int, image_bytes: bytes | None, reason_code: str | None):
    if not image_bytes:
        return None

    now = now_in_app_timezone()
    safe_reason = "".join(char for char in (reason_code or "LOW_FACE_QUALITY") if char.isalnum() or char == "_")
    relative_dir = Path("media") / "security_snapshots" / str(session_id)
    output_dir = BASE_DIR / relative_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{safe_reason}.jpg"
    output_path = output_dir / filename
    output_path.write_bytes(image_bytes)
    return str(relative_dir / filename).replace("\\", "/")


def _resolve_media_source_path(source_path: str | None):
    if not source_path:
        return None

    normalized = source_path.lstrip("/").replace("\\", "/")
    candidate = BASE_DIR / normalized
    try:
        resolved_base = BASE_DIR.resolve()
        resolved_candidate = candidate.resolve()
    except OSError:
        return None
    if resolved_base not in resolved_candidate.parents and resolved_candidate != resolved_base:
        return None
    if not resolved_candidate.is_file():
        return None
    return resolved_candidate


def save_face_unclear_snapshot_from_path(session_id: int, source_path: str | None, reason_code: str | None):
    source = _resolve_media_source_path(source_path)
    if source is None:
        return None

    now = now_in_app_timezone()
    safe_reason = "".join(char for char in (reason_code or "LOW_FACE_QUALITY") if char.isalnum() or char == "_")
    relative_dir = Path("media") / "security_snapshots" / str(session_id)
    output_dir = BASE_DIR / relative_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{now.strftime('%Y%m%d_%H%M%S')}_{safe_reason}.jpg"
    output_path = output_dir / filename
    shutil.copyfile(source, output_path)
    return str(relative_dir / filename).replace("\\", "/")


def create_alert(
    db,
    *,
    session_id: int,
    alert_type: str,
    student_id: int | None = None,
    image_bytes: bytes | None = None,
    source_image_path: str | None = None,
    captured_img: str | None = None,
    confidence: float | None = None,
    liveness_score: float | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    reason_code: str | None = None,
    quality_details: dict | None = None,
    note: str | None = None,
):
    normalized_type = alert_type.upper()
    if normalized_type not in ALERT_TYPES:
        raise ValueError(f"Unsupported security alert type: {alert_type}")

    alert_note = note
    if alert_note is None and normalized_type == "FACE_UNCLEAR":
        alert_note = json.dumps(
            {
                "reason_code": reason_code,
                "detection_confidence": confidence,
                "quality": quality_details,
            },
            ensure_ascii=False,
        )
    elif alert_note is None and reason_code:
        alert_note = f"reason_code={reason_code}"

    alert = SecurityAlert(
        session_id=session_id,
        alert_type=normalized_type,
        student_id=student_id,
        captured_img=captured_img
        or (
            (
                save_face_unclear_snapshot(session_id, image_bytes, reason_code)
                or save_face_unclear_snapshot_from_path(session_id, source_image_path, reason_code)
            )
            if normalized_type == "FACE_UNCLEAR"
            else save_alert_capture(session_id, image_bytes)
        ),
        confidence=confidence,
        liveness_score=liveness_score,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        note=alert_note,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
