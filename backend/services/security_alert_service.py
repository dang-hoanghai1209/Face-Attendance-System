from pathlib import Path
from uuid import uuid4

from models.security_alert import SecurityAlert
from services.timezone_service import now_in_app_timezone


BASE_DIR = Path(__file__).resolve().parents[1]
ALERT_TYPES = {"SPOOF", "UNKNOWN_FACE", "NOT_ENROLLED", "LATE_ENTRY"}


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


def create_alert(
    db,
    *,
    session_id: int,
    alert_type: str,
    student_id: int | None = None,
    image_bytes: bytes | None = None,
    captured_img: str | None = None,
    confidence: float | None = None,
    liveness_score: float | None = None,
    gps_lat: float | None = None,
    gps_lng: float | None = None,
    note: str | None = None,
):
    normalized_type = alert_type.upper()
    if normalized_type not in ALERT_TYPES:
        raise ValueError(f"Unsupported security alert type: {alert_type}")

    alert = SecurityAlert(
        session_id=session_id,
        alert_type=normalized_type,
        student_id=student_id,
        captured_img=captured_img or save_alert_capture(session_id, image_bytes),
        confidence=confidence,
        liveness_score=liveness_score,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        note=note,
    )
    db.add(alert)
    db.commit()
    db.refresh(alert)
    return alert
