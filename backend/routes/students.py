import re
from datetime import datetime, timedelta
from typing import Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.orm import Session

from database import get_db
from models.attendance import Attendance
from models.classroom import Classroom
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.face_embedding import FaceEmbedding
from models.recognition_attempt import RecognitionAttempt
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
from services.attendance_service import EARLY_CHECKIN_MINUTES, LATE_THRESHOLD_MINUTES
from services.auth_service import get_current_user, require_admin, resolve_student_for_user
from services.class_service import VALID_CLASS_SET, student_code_matches_class
from services.timezone_service import now_in_app_timezone


router = APIRouter(prefix="/students", tags=["Students"])

# ------------------------------------------------------------------ #
#  Các hằng số validation                                            #
# ------------------------------------------------------------------ #
VALID_CLASSES = VALID_CLASS_SET
VALID_DATA_SOURCES = {"real", "demo", "kaggle"}
VALID_REGISTRATION_METHODS = {"camera", "upload", "import"}

# Mã SV hợp lệ: bắt đầu bằng 63 hoặc 64, tiếp theo là đúng 6 chữ số.
# Tổng 8 ký tự: "63"/"64" + 6 số bất kỳ.
_CODE_RE = re.compile(r"^(63|64)\d{6}$")


def _validate_code(v: str) -> str:
    v = v.strip()
    if not _CODE_RE.match(v):
        raise ValueError(
            "Mã sinh viên không hợp lệ. "
            "Phải bắt đầu bằng 63 hoặc 64 và tiếp theo là đúng 6 chữ số (ví dụ: 63133870)."
        )
    return v


def _validate_class(v: Optional[str]) -> Optional[str]:
    if v is None:
        return v
    if v not in VALID_CLASSES:
        raise ValueError(
            f"Lớp không hợp lệ. Chỉ chấp nhận: {', '.join(sorted(VALID_CLASSES))}."
        )
    return v


def _ensure_code_matches_class(student_code: Optional[str], class_name: Optional[str]) -> None:
    if not student_code_matches_class(student_code, class_name):
        raise HTTPException(
            status_code=400,
            detail=f"Mã sinh viên {student_code} không khớp với lớp {class_name}.",
        )


def _validate_data_source(v: Optional[str]) -> str:
    value = (v or "real").strip().lower()
    if value not in VALID_DATA_SOURCES:
        raise ValueError(
            f"Nguồn dữ liệu không hợp lệ. Vui lòng chọn một trong các giá trị sau: {', '.join(sorted(VALID_DATA_SOURCES))}."
        )
    return value


def _validate_registration_method(v: Optional[str]) -> Optional[str]:
    if v is None:
        return None
    value = v.strip().lower()
    if value not in VALID_REGISTRATION_METHODS:
        raise ValueError(
            f"Phương thức đăng ký không hợp lệ. Vui lòng chọn một trong các giá trị sau: {', '.join(sorted(VALID_REGISTRATION_METHODS))}."
        )
    return value


# ------------------------------------------------------------------ #
#  Schema                                                            #
# ------------------------------------------------------------------ #
class StudentBase(BaseModel):
    student_code: str
    full_name: str
    class_name: Optional[str] = None
    data_source: Literal["real", "demo", "kaggle"] = "real"
    registration_method: Optional[Literal["camera", "upload", "import"]] = None
    is_demo: bool = False

    @field_validator("student_code")
    @classmethod
    def check_code(cls, v):
        return _validate_code(v)

    @field_validator("class_name")
    @classmethod
    def check_class(cls, v):
        return _validate_class(v)

    @field_validator("data_source")
    @classmethod
    def check_data_source(cls, v):
        return _validate_data_source(v)

    @field_validator("registration_method")
    @classmethod
    def check_registration_method(cls, v):
        return _validate_registration_method(v)


class StudentUpdate(BaseModel):
    student_code: Optional[str] = None
    full_name: Optional[str] = None
    class_name: Optional[str] = None
    data_source: Optional[Literal["real", "demo", "kaggle"]] = None
    registration_method: Optional[Literal["camera", "upload", "import"]] = None
    is_demo: Optional[bool] = None

    @field_validator("student_code")
    @classmethod
    def check_code(cls, v):
        if v is None:
            return v
        return _validate_code(v)

    @field_validator("class_name")
    @classmethod
    def check_class(cls, v):
        return _validate_class(v)

    @field_validator("data_source")
    @classmethod
    def check_data_source(cls, v):
        if v is None:
            return v
        return _validate_data_source(v)

    @field_validator("registration_method")
    @classmethod
    def check_registration_method(cls, v):
        return _validate_registration_method(v)


def _format_time(value):
    return value.strftime("%H:%M") if value else None


def _mobile_session_status(session: ClassSession, now_value: datetime):
    if not session.start_time:
        return "closed", None

    session_start = datetime.combine(session.session_date, session.start_time)
    attendance_open_at = session_start - timedelta(minutes=EARLY_CHECKIN_MINUTES)
    attendance_deadline = session_start + timedelta(minutes=LATE_THRESHOLD_MINUTES)
    if now_value < attendance_open_at:
        return "not_started", attendance_deadline
    if now_value <= attendance_deadline:
        return "open_for_attendance", attendance_deadline
    return "closed", attendance_deadline


@router.get("/me/active-sessions")
def get_my_active_sessions(
    current_user=Depends(get_current_user),
    student_id: int | None = None,
    db: Session = Depends(get_db),
):
    student = resolve_student_for_user(db, current_user)
    if student is None:
        if student_id is None:
            raise HTTPException(status_code=400, detail="Vui lòng cung cấp student_id khi dùng chế độ dev.")
        student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")

    now_value = now_in_app_timezone()
    rows = (
        db.query(ClassSession, CourseSection, Subject, Classroom)
        .join(CourseSection, ClassSession.section_id == CourseSection.id)
        .join(Enrollment, Enrollment.course_section_id == CourseSection.id)
        .join(Subject, CourseSection.subject_id == Subject.id)
        .outerjoin(Classroom, ClassSession.classroom_id == Classroom.id)
        .filter(
            Enrollment.student_id == student.id,
            Enrollment.status == "active",
        )
        .order_by(ClassSession.session_date.asc(), ClassSession.start_time.asc())
        .all()
    )

    items = []
    for session, section, subject, classroom in rows:
        status, attendance_deadline = _mobile_session_status(session, now_value)
        items.append(
            {
                "session_id": session.id,
                "section_id": section.id,
                "subject_name": subject.subject_name,
                "section_code": section.section_code,
                "classroom_id": classroom.id if classroom else None,
                "classroom_name": classroom.name if classroom else None,
                "classroom_gps_lat": classroom.gps_lat if classroom else None,
                "classroom_gps_lng": classroom.gps_lng if classroom else None,
                "radius_meters": classroom.radius_meters if classroom else None,
                "session_date": session.session_date.isoformat() if session.session_date else None,
                "start_time": _format_time(session.start_time),
                "end_time": _format_time(session.end_time),
                "attendance_deadline": _format_time(attendance_deadline),
                "status": status,
            }
        )
    return items


@router.get("/")
def get_all_students(_current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Student).order_by(Student.full_name.asc()).all()


@router.post("/")
def create_student(student: StudentBase, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    _ensure_code_matches_class(student.student_code, student.class_name)

    existing = db.query(Student).filter(Student.student_code == student.student_code).first()
    if existing:
        raise HTTPException(status_code=400, detail="Mã sinh viên đã tồn tại.")

    db_student = Student(**student.model_dump())
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


@router.put("/{student_id}")
def update_student(
    student_id: int,
    student_data: StudentUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Sinh viên không hợp lệ.")

    updates = student_data.model_dump(exclude_unset=True)
    next_student_code = updates.get("student_code", student.student_code)
    next_class_name = updates.get("class_name", student.class_name)
    _ensure_code_matches_class(next_student_code, next_class_name)

    if "student_code" in updates:
        duplicate = (
            db.query(Student)
            .filter(Student.student_code == updates["student_code"], Student.id != student_id)
            .first()
        )
        if duplicate:
            raise HTTPException(status_code=400, detail="Mã sinh viên đã tồn tại.")

    for field, value in updates.items():
        setattr(student, field, value)

    db.commit()
    db.refresh(student)
    return student


@router.delete("/{student_id}")
def delete_student(student_id: int, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Sinh viên không hợp lệ.")

    db.query(Attendance).filter(Attendance.student_id == student_id).delete()
    db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student_id).delete()
    db.query(RecognitionAttempt).filter(RecognitionAttempt.predicted_student_id == student_id).delete()
    db.delete(student)
    db.commit()
    return {"message": f"Đã xóa sinh viên {student.full_name}."}
