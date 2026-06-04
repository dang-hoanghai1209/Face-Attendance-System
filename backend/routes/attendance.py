import logging
from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from services import attendance_service
from services.auth_service import get_current_user, require_admin, require_role


router = APIRouter(prefix="/attendance", tags=["Attendance"])
logger = logging.getLogger("face_attendance")
require_attendance_editor = require_role("admin", "teacher")


class AttendanceCheckIn(BaseModel):
    student_code: str
    session_id: int
    confidence: Optional[float] = None
    image_path: Optional[str] = None


class AttendanceCheckOut(BaseModel):
    student_code: str
    session_id: int
    confidence: Optional[float] = None


class ManualAttendanceCreate(BaseModel):
    student_code: str
    session_id: int
    note: Optional[str] = None
    audit_id: Optional[int] = None


@router.post("/")
def record_attendance(data: AttendanceCheckIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(
        "attendance checkin alias request: session_id=%s student_code=%s user=%s",
        data.session_id,
        data.student_code,
        current_user.username,
    )
    return attendance_service.record_checkin(
        db,
        student_code=data.student_code,
        session_id=data.session_id,
        confidence=data.confidence,
        image_path=data.image_path,
    )


@router.post("/checkin")
def record_checkin(data: AttendanceCheckIn, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    logger.info(
        "attendance checkin request: session_id=%s student_code=%s user=%s",
        data.session_id,
        data.student_code,
        current_user.username,
    )
    return attendance_service.record_checkin(
        db,
        student_code=data.student_code,
        session_id=data.session_id,
        confidence=data.confidence,
        image_path=data.image_path,
    )


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


@router.post("/manual")
def record_manual_attendance(
    data: ManualAttendanceCreate,
    current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    logger.info(
        "attendance manual request: session_id=%s student_code=%s audit_id=%s note_present=%s user=%s",
        data.session_id,
        data.student_code,
        data.audit_id,
        data.note is not None,
        current_user.username,
    )
    return attendance_service.record_manual_attendance(
        db,
        student_code=data.student_code,
        session_id=data.session_id,
        note=data.note,
        audit_id=data.audit_id,
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
