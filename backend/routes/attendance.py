import logging
from typing import Any, Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.attendance import Attendance
from models.student import Student
from services import attendance_service
from services.audit_service import audit_details, audit_safely, model_snapshot
from services.auth_service import get_current_user, require_role, require_student_self_or_role


router = APIRouter(prefix="/attendance", tags=["Attendance"])
logger = logging.getLogger("face_attendance")
require_attendance_editor = require_role("admin", "teacher")
ATTENDANCE_AUDIT_FIELDS = (
    "student_id",
    "session_id",
    "check_in_at",
    "check_out_at",
    "check_in_conf",
    "check_out_conf",
    "check_in_img",
    "status",
    "note",
    "gps_lat",
    "gps_lng",
    "gps_accuracy",
    "distance_meters",
    "liveness_passed",
    "scan_count",
    "last_scan_at",
)


class AttendanceCheckIn(BaseModel):
    student_code: Optional[str] = None
    session_id: int
    confidence: Optional[float] = None
    image_path: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    gps_accuracy: Optional[float] = None
    liveness_passed: Optional[bool] = None
    liveness_score: Optional[float] = None
    recognition_status: Optional[str] = None
    mode: Optional[str] = None
    reason_code: Optional[str] = None
    quality: Optional[dict[str, Any]] = None


class AttendanceCheckOut(BaseModel):
    student_code: str
    session_id: int
    confidence: Optional[float] = None


def _attendance_snapshot_by_student_code(db: Session, student_code: str, session_id: int):
    if not student_code:
        return None
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        return None
    record = (
        db.query(Attendance)
        .filter(Attendance.student_id == student.id, Attendance.session_id == session_id)
        .first()
    )
    return model_snapshot(record, ATTENDANCE_AUDIT_FIELDS)


def _audit_attendance_response(db: Session, action: str, current_user, data, response, request=None, old_value=None):
    payload = response if isinstance(response, dict) else {}
    new_value = _attendance_snapshot_by_student_code(db, data.student_code, data.session_id)
    audit_safely(
        db,
        action=action,
        actor_user=current_user,
        target_type="attendance",
        target_id=payload.get("record_id") or payload.get("data", {}).get("record_id"),
        details=audit_details(
            request=request,
            old_value=old_value,
            new_value=new_value,
            student_code=data.student_code,
            session_id=data.session_id,
            status=payload.get("status"),
        ),
    )


def _checkin_response(db: Session, data: AttendanceCheckIn):
    try:
        return attendance_service.record_checkin(
            db,
            student_code=data.student_code,
            session_id=data.session_id,
            confidence=data.confidence,
            image_path=data.image_path,
            gps_lat=data.gps_lat,
            gps_lng=data.gps_lng,
            gps_accuracy=data.gps_accuracy,
            liveness_passed=data.liveness_passed,
            liveness_score=data.liveness_score,
            recognition_status=data.recognition_status,
            reason_code=data.reason_code,
            quality_details=data.quality,
        )
    except HTTPException as exc:
        if isinstance(exc.detail, dict) and exc.detail.get("status"):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        raise


@router.post("/")
def record_attendance(
    data: AttendanceCheckIn,
    request: Request = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(
        "attendance checkin alias request: session_id=%s student_code=%s user=%s",
        data.session_id,
        data.student_code,
        current_user.username,
    )
    if data.student_code:
        require_student_self_or_role(db, current_user, data.student_code, "admin", "teacher")
    elif (data.recognition_status or "").upper() != "FACE_UNCLEAR":
        raise HTTPException(status_code=400, detail="Thiáº¿u mÃ£ sinh viÃªn cho Ä‘iá»ƒm danh.")
    old_value = _attendance_snapshot_by_student_code(db, data.student_code, data.session_id)
    response = _checkin_response(db, data)
    _audit_attendance_response(db, "attendance_checkin", current_user, data, response, request, old_value)
    return response


@router.post("/checkin")
def record_checkin(
    data: AttendanceCheckIn,
    request: Request = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(
        "attendance checkin request: session_id=%s student_code=%s user=%s",
        data.session_id,
        data.student_code,
        current_user.username,
    )
    if data.student_code:
        require_student_self_or_role(db, current_user, data.student_code, "admin", "teacher")
    elif (data.recognition_status or "").upper() != "FACE_UNCLEAR":
        raise HTTPException(status_code=400, detail="Thiáº¿u mÃ£ sinh viÃªn cho Ä‘iá»ƒm danh.")
    old_value = _attendance_snapshot_by_student_code(db, data.student_code, data.session_id)
    response = _checkin_response(db, data)
    _audit_attendance_response(db, "attendance_checkin", current_user, data, response, request, old_value)
    return response


@router.post("/checkout")
def record_checkout(
    data: AttendanceCheckOut,
    request: Request = None,
    current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    logger.info(
        "attendance checkout request: session_id=%s student_code=%s user=%s",
        data.session_id,
        data.student_code,
        current_user.username,
    )
    require_student_self_or_role(db, current_user, data.student_code, "admin", "teacher")
    old_value = _attendance_snapshot_by_student_code(db, data.student_code, data.session_id)
    response = attendance_service.record_checkout(
        db,
        student_code=data.student_code,
        session_id=data.session_id,
        confidence=data.confidence,
    )
    _audit_attendance_response(db, "attendance_checkout", current_user, data, response, request, old_value)
    return response


@router.delete("/{attendance_id}")
def delete_attendance_record(
    attendance_id: int,
    request: Request = None,
    current_user=Depends(require_attendance_editor),
    db: Session = Depends(get_db),
):
    logger.info(
        "attendance delete request: attendance_id=%s user=%s role=%s",
        attendance_id,
        current_user.username,
        current_user.role,
    )
    old_record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    old_value = model_snapshot(old_record, ATTENDANCE_AUDIT_FIELDS)
    response = attendance_service.delete_attendance_record(db, attendance_id)
    audit_safely(
        db,
        action="attendance_deleted",
        actor_user=current_user,
        target_type="attendance",
        target_id=attendance_id,
        details=audit_details(request=request, old_value=old_value, **(response.get("data") or {})),
    )
    return response


@router.get("/session/{session_id}")
def get_session_attendance(session_id: int, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return attendance_service.get_session_attendance(db, session_id)


@router.get("/summary/{class_name}")
def get_class_attendance_summary(class_name: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return attendance_service.get_class_attendance_summary(db, class_name)
