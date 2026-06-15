import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services import attendance_service
from services.auth_service import get_current_user, require_role


router = APIRouter(prefix="/attendance", tags=["Attendance"])
logger = logging.getLogger("face_attendance")
require_attendance_editor = require_role("admin", "teacher", "lecturer")


class AttendanceCheckIn(BaseModel):
    student_code: str
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


class AttendanceCheckOut(BaseModel):
    student_code: str
    session_id: int
    confidence: Optional[float] = None


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
        )
    except HTTPException as exc:
        if isinstance(exc.detail, dict) and exc.detail.get("status"):
            return JSONResponse(status_code=exc.status_code, content=exc.detail)
        raise


@router.post("/")
def record_attendance(data: AttendanceCheckIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(
        "attendance checkin alias request: session_id=%s student_code=%s user=%s",
        data.session_id,
        data.student_code,
        current_user.username,
    )
    return _checkin_response(db, data)


@router.post("/checkin")
def record_checkin(data: AttendanceCheckIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(
        "attendance checkin request: session_id=%s student_code=%s user=%s",
        data.session_id,
        data.student_code,
        current_user.username,
    )
    return _checkin_response(db, data)


@router.post("/checkout")
def record_checkout(data: AttendanceCheckOut, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(
        "attendance checkout request: session_id=%s student_code=%s user=%s",
        data.session_id,
        data.student_code,
        current_user.username,
    )
    return attendance_service.record_checkout(
        db,
        student_code=data.student_code,
        session_id=data.session_id,
        confidence=data.confidence,
    )


@router.delete("/{attendance_id}")
def delete_attendance_record(
    attendance_id: int,
    current_user=Depends(require_attendance_editor),
    db: Session = Depends(get_db),
):
    logger.info(
        "attendance delete request: attendance_id=%s user=%s role=%s",
        attendance_id,
        current_user.username,
        current_user.role,
    )
    return attendance_service.delete_attendance_record(db, attendance_id)


@router.get("/session/{session_id}")
def get_session_attendance(session_id: int, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return attendance_service.get_session_attendance(db, session_id)


@router.get("/summary/{class_name}")
def get_class_attendance_summary(class_name: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return attendance_service.get_class_attendance_summary(db, class_name)
