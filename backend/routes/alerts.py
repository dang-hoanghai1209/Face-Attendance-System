from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.security_alert import SecurityAlert
from models.student import Student
from services.audit_service import audit_details, audit_safely, model_snapshot
from services.auth_service import get_current_user, require_role
from services.security_alert_service import ALERT_TYPES
from services.timezone_service import now_in_app_timezone


router = APIRouter(prefix="/alerts", tags=["Security Alerts"])
require_alert_editor = require_role("admin", "teacher")
SECURITY_ALERT_AUDIT_FIELDS = (
    "session_id",
    "alert_type",
    "student_id",
    "captured_img",
    "confidence",
    "liveness_score",
    "gps_lat",
    "gps_lng",
    "dismissed",
    "dismissed_by",
    "dismissed_at",
    "note",
)


class AlertDismissRequest(BaseModel):
    note: Optional[str] = None
    dismissed_by: Optional[str] = None


def _serialize_alert(db: Session, alert: SecurityAlert):
    student = db.query(Student).filter(Student.id == alert.student_id).first() if alert.student_id else None
    return {
        "id": alert.id,
        "session_id": alert.session_id,
        "alert_type": alert.alert_type,
        "student_id": alert.student_id,
        "student_code": student.student_code if student else None,
        "full_name": student.full_name if student else None,
        "class_name": student.class_name if student else None,
        "captured_img": alert.captured_img,
        "confidence": alert.confidence,
        "liveness_score": alert.liveness_score,
        "gps_lat": alert.gps_lat,
        "gps_lng": alert.gps_lng,
        "dismissed": alert.dismissed,
        "dismissed_by": alert.dismissed_by,
        "dismissed_at": alert.dismissed_at.isoformat() if alert.dismissed_at else None,
        "note": alert.note,
        "created_at": alert.created_at.isoformat() if alert.created_at else None,
    }


def _session_alert_query(db: Session, session_id: int, dismissed: Optional[bool] = None):
    query = db.query(SecurityAlert).filter(SecurityAlert.session_id == session_id)
    if dismissed is not None:
        query = query.filter(SecurityAlert.dismissed == dismissed)
    return query.order_by(SecurityAlert.created_at.desc(), SecurityAlert.id.desc())


@router.get("/session/{session_id}")
def get_session_alerts(
    session_id: int,
    dismissed: Optional[bool] = None,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    alerts = _session_alert_query(db, session_id, dismissed=dismissed).all()
    return [_serialize_alert(db, alert) for alert in alerts]


@router.get("/session/{session_id}/active")
def get_active_session_alerts(session_id: int, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    alerts = _session_alert_query(db, session_id, dismissed=False).all()
    return [_serialize_alert(db, alert) for alert in alerts]


@router.post("/{alert_id}/dismiss")
def dismiss_alert(
    alert_id: int,
    data: AlertDismissRequest,
    request: Request = None,
    current_user=Depends(require_alert_editor),
    db: Session = Depends(get_db),
):
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Không tìm thấy cảnh báo bảo mật.")

    old_value = model_snapshot(alert, SECURITY_ALERT_AUDIT_FIELDS)
    student = db.query(Student).filter(Student.id == alert.student_id).first() if alert.student_id else None
    alert.dismissed = True
    alert.dismissed_at = now_in_app_timezone()
    alert.dismissed_by = data.dismissed_by or getattr(current_user, "username", None)
    if data.note is not None:
        alert.note = data.note
    db.commit()
    db.refresh(alert)
    audit_safely(
        db,
        action="security_alert_dismissed",
        actor_user=current_user,
        target_type="security_alert",
        target_id=alert.id,
        details=audit_details(
            request=request,
            old_value=old_value,
            new_value=model_snapshot(alert, SECURITY_ALERT_AUDIT_FIELDS),
            session_id=alert.session_id,
            student_id=alert.student_id,
            student_code=student.student_code if student else None,
            reason=data.note,
        ),
    )
    return _serialize_alert(db, alert)


@router.get("/session/{session_id}/count")
def count_session_alerts(session_id: int, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    active_alerts = (
        db.query(SecurityAlert)
        .filter(SecurityAlert.session_id == session_id, SecurityAlert.dismissed == False)  # noqa: E712
        .all()
    )
    by_type = {alert_type: 0 for alert_type in sorted(ALERT_TYPES)}
    for alert in active_alerts:
        by_type[alert.alert_type] = by_type.get(alert.alert_type, 0) + 1

    return {
        "session_id": session_id,
        "total_active": len(active_alerts),
        "by_type": by_type,
    }
