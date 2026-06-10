from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
from services.auth_service import get_current_user, require_admin


router = APIRouter(prefix="/course-sections", tags=["Course Sections"])
VALID_SECTION_STATUSES = {"open", "closed", "archived"}


class CourseSectionCreate(BaseModel):
    section_code: str
    subject_id: int
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    lecturer_user_id: Optional[int] = None
    lecturer_name: Optional[str] = None
    min_students: Optional[int] = None
    max_students: Optional[int] = None
    status: str = "open"

    @field_validator("section_code")
    @classmethod
    def validate_section_code(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Vui lòng nhập mã lớp học phần.")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in VALID_SECTION_STATUSES:
            raise ValueError("Trạng thái lớp học phần không hợp lệ.")
        return value


class CourseSectionUpdate(BaseModel):
    section_code: Optional[str] = None
    subject_id: Optional[int] = None
    semester: Optional[str] = None
    academic_year: Optional[str] = None
    lecturer_user_id: Optional[int] = None
    lecturer_name: Optional[str] = None
    min_students: Optional[int] = None
    max_students: Optional[int] = None
    status: Optional[str] = None

    @field_validator("section_code")
    @classmethod
    def validate_section_code(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Vui lòng nhập mã lớp học phần.")
        return value

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value is not None and value not in VALID_SECTION_STATUSES:
            raise ValueError("Trạng thái lớp học phần không hợp lệ.")
        return value


def _serialize_section(db: Session, section: CourseSection):
    subject = db.query(Subject).filter(Subject.id == section.subject_id).first()
    student_count = (
        db.query(Enrollment)
        .filter(Enrollment.course_section_id == section.id, Enrollment.status == "active")
        .count()
    )
    return {
        "id": section.id,
        "section_code": section.section_code,
        "subject_id": section.subject_id,
        "subject_code": subject.subject_code if subject else None,
        "subject_name": subject.subject_name if subject else None,
        "semester": section.semester,
        "academic_year": section.academic_year,
        "lecturer_user_id": section.lecturer_user_id,
        "lecturer_name": section.lecturer_name,
        "min_students": section.min_students,
        "max_students": section.max_students,
        "status": section.status,
        "student_count": student_count,
        "created_at": section.created_at.isoformat() if section.created_at else None,
        "updated_at": section.updated_at.isoformat() if section.updated_at else None,
    }


def _ensure_subject_exists(db: Session, subject_id: int):
    if not db.query(Subject).filter(Subject.id == subject_id).first():
        raise HTTPException(status_code=404, detail="Không tìm thấy học phần.")


@router.get("/")
def get_course_sections(
    semester: Optional[str] = None,
    academic_year: Optional[str] = None,
    subject_id: Optional[int] = None,
    status: Optional[str] = None,
    _current_user=Depends(get_current_user),
    db: Session = Depends(get_db),
):
    query = db.query(CourseSection)
    if semester:
        query = query.filter(CourseSection.semester == semester)
    if academic_year:
        query = query.filter(CourseSection.academic_year == academic_year)
    if subject_id:
        query = query.filter(CourseSection.subject_id == subject_id)
    if status:
        query = query.filter(CourseSection.status == status)
    sections = query.order_by(CourseSection.section_code.asc()).all()
    return [_serialize_section(db, section) for section in sections]


@router.post("/")
def create_course_section(data: CourseSectionCreate, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    _ensure_subject_exists(db, data.subject_id)
    section = CourseSection(**data.model_dump())
    db.add(section)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Mã lớp học phần đã tồn tại.") from exc
    db.refresh(section)
    return _serialize_section(db, section)


@router.put("/{section_id}")
def update_course_section(
    section_id: int,
    data: CourseSectionUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần.")
    updates = data.model_dump(exclude_unset=True)
    if "subject_id" in updates:
        _ensure_subject_exists(db, updates["subject_id"])
    for field, value in updates.items():
        setattr(section, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Mã lớp học phần đã tồn tại.") from exc
    db.refresh(section)
    return _serialize_section(db, section)


@router.delete("/{section_id}")
def delete_course_section(section_id: int, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần.")
    used = db.query(ClassSession).filter(ClassSession.section_id == section_id).first()
    if used:
        raise HTTPException(status_code=400, detail="Không thể xóa lớp học phần đang có buổi học.")
    db.query(Enrollment).filter(Enrollment.course_section_id == section_id).delete()
    db.delete(section)
    db.commit()
    return {"message": "Đã xóa lớp học phần."}


@router.get("/{section_id}/students")
def get_course_section_students(section_id: int, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    section = db.query(CourseSection).filter(CourseSection.id == section_id).first()
    if not section:
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần.")
    rows = (
        db.query(Enrollment, Student)
        .join(Student, Enrollment.student_id == Student.id)
        .filter(Enrollment.course_section_id == section_id)
        .order_by(Student.full_name.asc())
        .all()
    )
    return [
        {
            "enrollment_id": enrollment.id,
            "student_id": student.id,
            "student_code": student.student_code,
            "full_name": student.full_name,
            "class_name": student.class_name,
            "face_status": student.face_status,
            "enrollment_status": enrollment.status,
        }
        for enrollment, student in rows
    ]
