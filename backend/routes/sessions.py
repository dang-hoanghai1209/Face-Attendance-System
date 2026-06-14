from datetime import date, time, timedelta
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
from models.subject import Subject
from services.auth_service import get_current_user, require_admin
from services.class_service import VALID_CLASS_SET


router = APIRouter(prefix="/sessions", tags=["Sessions"])

VALID_CLASSES = VALID_CLASS_SET
MISSING_GPS_MESSAGE = "Thiếu tọa độ GPS của buổi học"


def _validate_class(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    v_stripped = v.strip()
    if not v_stripped:
        raise ValueError("Tên lớp không được để trống.")
    if len(v_stripped) > 50:
        raise ValueError("Tên lớp không được dài quá 50 ký tự.")
    return v_stripped


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
    session_number: Optional[int] = None
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
    session_number: Optional[int] = None
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
    weeks: Optional[int] = 1

    @field_validator("weeks")
    @classmethod
    def check_weeks(cls, v):
        if v is not None and (v < 1 or v > 20):
            raise ValueError("Số tuần học phải từ 1 đến 20.")
        return v

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

    existing_count = db.query(ClassSession).filter(ClassSession.section_id == section.id).count()
    weeks_to_create = session_data.weeks or 1
    created_sessions = []

    for i in range(weeks_to_create):
        current_date = session_data.session_date + timedelta(weeks=i)
        current_number = existing_count + i + 1

        note_suffix = f"[Buổi {current_number}]"
        if session_data.note:
            note_content = f"{session_data.note.strip()} {note_suffix}"
        else:
            note_content = note_suffix

        new_session = ClassSession(
            subject=subject.subject_name if subject else section.section_code,
            class_name=section.section_code,
            section_id=section.id,
            classroom_id=classroom.id,
            latitude=classroom.gps_lat,
            longitude=classroom.gps_lng,
            radius_meters=classroom.radius_meters,
            room_name=classroom.name,
            session_date=current_date,
            start_time=session_data.start_time,
            end_time=session_data.end_time,
            session_number=current_number,
            note=note_content,
            created_by=section.lecturer_name,
        )
        db.add(new_session)
        created_sessions.append(new_session)

    db.commit()
    for s in created_sessions:
        db.refresh(s)

    return created_sessions[0]


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
