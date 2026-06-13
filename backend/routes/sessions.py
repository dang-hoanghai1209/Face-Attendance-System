from datetime import date, time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator, model_validator
from sqlalchemy.orm import Session

from database import get_db
from models.attendance import Attendance
from models.attendance_scan import AttendanceScan
from models.classroom import Classroom
from models.course_section import CourseSection
from models.recognition_attempt import RecognitionAttempt
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
from services.auth_service import get_current_user, require_admin
from services.class_service import VALID_CLASS_SET


router = APIRouter(prefix="/sessions", tags=["Sessions"])

VALID_CLASSES = VALID_CLASS_SET
MIN_STUDENTS_PER_SESSION_CLASS = 5
MISSING_GPS_MESSAGE = "Thiếu tọa độ GPS của buổi học"
MIN_STUDENTS_MESSAGE = "Lớp cần tối thiểu 5 sinh viên"


def _validate_class(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in VALID_CLASSES:
        raise ValueError(
            f"Lớp không hợp lệ. Chỉ chấp nhận: {', '.join(sorted(VALID_CLASSES))}."
        )
    return v


def _validate_time_range(start_time: Optional[time], end_time: Optional[time]) -> None:
    if start_time is None:
        raise ValueError("Vui lòng nhập thời gian bắt đầu.")
    if end_time is None:
        raise ValueError("Vui lòng nhập thời gian kết thúc.")
    if end_time <= start_time:
        raise ValueError("Thời gian kết thúc phải sau thời gian bắt đầu.")


class SessionCreate(BaseModel):
    subject: str
    class_name: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    radius_meters: Optional[int] = 50
    room_name: Optional[str] = None
    session_date: date
    start_time: time
    end_time: time
    created_by: Optional[str] = None

    @field_validator("class_name")
    @classmethod
    def check_class(cls, v):
        return _validate_class(v)

    @model_validator(mode="after")
    def check_time_range(self):
        _validate_time_range(self.start_time, self.end_time)
        return self


class SessionUpdate(BaseModel):
    subject: Optional[str] = None
    class_name: Optional[str] = None
    session_date: Optional[date] = None
    start_time: Optional[time] = None
    end_time: Optional[time] = None
    created_by: Optional[str] = None

    @field_validator("class_name")
    @classmethod
    def check_class(cls, v):
        return _validate_class(v)


class SessionFromSectionCreate(BaseModel):
    section_id: int
    classroom_id: int
    session_date: date
    start_time: time
    end_time: time
    note: Optional[str] = None

    @model_validator(mode="after")
    def check_time_range(self):
        _validate_time_range(self.start_time, self.end_time)
        return self


@router.get("/")
def get_all_sessions(_current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(ClassSession).order_by(ClassSession.session_date.desc()).all()


@router.post("/")
def create_session(session_data: SessionCreate, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    if session_data.latitude is None or session_data.longitude is None:
        raise HTTPException(status_code=422, detail=MISSING_GPS_MESSAGE)

    student_count = db.query(Student).filter(Student.class_name == session_data.class_name).count()
    if student_count < MIN_STUDENTS_PER_SESSION_CLASS:
        raise HTTPException(status_code=422, detail=MIN_STUDENTS_MESSAGE)

    new_session = ClassSession(**session_data.model_dump())
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


@router.post("/from-section")
def create_session_from_section(
    session_data: SessionFromSectionCreate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    section = db.query(CourseSection).filter(CourseSection.id == session_data.section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần.")

    classroom = db.query(Classroom).filter(Classroom.id == session_data.classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng học.")
    if not classroom.is_active:
        raise HTTPException(status_code=400, detail="Phòng học này đang bị vô hiệu hóa.")

    subject = db.query(Subject).filter(Subject.id == section.subject_id).first()
    new_session = ClassSession(
        subject=subject.subject_name if subject else section.section_code,
        class_name=section.section_code,
        section_id=section.id,
        classroom_id=classroom.id,
        latitude=classroom.gps_lat,
        longitude=classroom.gps_lng,
        radius_meters=classroom.radius_meters,
        room_name=classroom.name,
        session_date=session_data.session_date,
        start_time=session_data.start_time,
        end_time=session_data.end_time,
        note=session_data.note,
        created_by=section.lecturer_name,
    )
    db.add(new_session)
    db.commit()
    db.refresh(new_session)
    return new_session


@router.put("/{session_id}")
def update_session(
    session_id: int,
    session_data: SessionUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Buổi học không hợp lệ.")

    updates = session_data.model_dump(exclude_unset=True)
    next_start_time = updates.get("start_time", session.start_time)
    next_end_time = updates.get("end_time", session.end_time)
    try:
        _validate_time_range(next_start_time, next_end_time)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    for field, value in updates.items():
        setattr(session, field, value)

    db.commit()
    db.refresh(session)
    return session


@router.delete("/{session_id}")
def delete_session(session_id: int, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Buổi học không hợp lệ.")

    attendance_ids = [
        row.id
        for row in db.query(Attendance.id).filter(Attendance.session_id == session_id).all()
    ]
    if attendance_ids:
        db.query(AttendanceScan).filter(AttendanceScan.attendance_id.in_(attendance_ids)).delete(
            synchronize_session=False
        )
    db.query(Attendance).filter(Attendance.session_id == session_id).delete(synchronize_session=False)
    db.query(RecognitionAttempt).filter(RecognitionAttempt.session_id == session_id).delete()
    db.delete(session)
    db.commit()
    return {"message": f"Đã xóa buổi học {session_id}."}
