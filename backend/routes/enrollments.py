from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.student import Student
from models.subject import Subject
from services.auth_service import get_current_user, require_admin


router = APIRouter(tags=["Enrollments"])
VALID_ENROLLMENT_STATUSES = {"active", "dropped", "completed"}


class EnrollmentCreate(BaseModel):
    course_section_id: int
    student_id: int
    status: str = "active"

    @field_validator("status")
    @classmethod
    def validate_status(cls, value):
        if value not in VALID_ENROLLMENT_STATUSES:
            raise ValueError("Trạng thái đăng ký học phần không hợp lệ.")
        return value


def _serialize_enrollment(db: Session, enrollment: Enrollment):
    section = db.query(CourseSection).filter(CourseSection.id == enrollment.course_section_id).first()
    subject = db.query(Subject).filter(Subject.id == section.subject_id).first() if section else None
    student = db.query(Student).filter(Student.id == enrollment.student_id).first()
    return {
        "id": enrollment.id,
        "course_section_id": enrollment.course_section_id,
        "section_code": section.section_code if section else None,
        "subject_id": section.subject_id if section else None,
        "subject_code": subject.subject_code if subject else None,
        "subject_name": subject.subject_name if subject else None,
        "student_id": enrollment.student_id,
        "student_code": student.student_code if student else None,
        "full_name": student.full_name if student else None,
        "status": enrollment.status,
        "created_at": enrollment.created_at.isoformat() if enrollment.created_at else None,
        "updated_at": enrollment.updated_at.isoformat() if enrollment.updated_at else None,
    }


@router.post("/enrollments")
def create_enrollment(data: EnrollmentCreate, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    if not db.query(CourseSection).filter(CourseSection.id == data.course_section_id).first():
        raise HTTPException(status_code=404, detail="Không tìm thấy lớp học phần.")
    if not db.query(Student).filter(Student.id == data.student_id).first():
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")

    enrollment = Enrollment(**data.model_dump())
    db.add(enrollment)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Sinh viên đã có trong lớp học phần này.") from exc
    db.refresh(enrollment)
    return _serialize_enrollment(db, enrollment)


@router.delete("/enrollments/{enrollment_id}")
def delete_enrollment(enrollment_id: int, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Không tìm thấy đăng ký học phần.")
    db.delete(enrollment)
    db.commit()
    return {"message": "Đã xóa đăng ký học phần."}


@router.get("/students/{student_id}/enrollments")
def get_student_enrollments(student_id: int, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    if not db.query(Student).filter(Student.id == student_id).first():
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")
    enrollments = (
        db.query(Enrollment)
        .filter(Enrollment.student_id == student_id)
        .order_by(Enrollment.created_at.desc())
        .all()
    )
    return [_serialize_enrollment(db, enrollment) for enrollment in enrollments]
