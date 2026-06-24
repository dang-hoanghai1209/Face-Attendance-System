from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
from services.audit_service import audit_details, audit_safely, model_snapshot
from services.auth_service import get_current_user, require_admin


router = APIRouter(tags=["Enrollments"])
VALID_ENROLLMENT_STATUSES = {"active", "dropped", "completed"}
ENROLLMENT_AUDIT_FIELDS = ("session_id", "course_section_id", "student_id", "status", "note")


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


class SessionEnrollmentRequest(BaseModel):
    student_codes: list[str]


class SessionEnrollmentImportRequest(BaseModel):
    class_name: str


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


def _get_session_or_404(db: Session, session_id: int):
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail=f"Không tìm thấy buổi học #{session_id}.")
    return session


def _serialize_session_enrollment(db: Session, enrollment: Enrollment):
    student = db.query(Student).filter(Student.id == enrollment.student_id).first()
    return {
        "id": enrollment.id,
        "session_id": enrollment.session_id,
        "student_id": enrollment.student_id,
        "student_code": student.student_code if student else None,
        "full_name": student.full_name if student else None,
        "class_name": student.class_name if student else None,
        "enrolled_at": enrollment.enrolled_at.isoformat() if enrollment.enrolled_at else None,
        "note": enrollment.note,
    }


def _session_enrollment_query(db: Session, session_id: int):
    return (
        db.query(Enrollment)
        .filter(Enrollment.session_id == session_id)
        .order_by(Enrollment.enrolled_at.asc(), Enrollment.id.asc())
    )


def _add_students_to_session_enrollment(db: Session, session_id: int, students: list[Student]):
    added = []
    skipped = []

    for student in students:
        existing = (
            db.query(Enrollment)
            .filter(Enrollment.session_id == session_id, Enrollment.student_id == student.id)
            .first()
        )
        if existing:
            skipped.append(student.student_code)
            continue

        enrollment = Enrollment(session_id=session_id, student_id=student.id, status="active")
        db.add(enrollment)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            skipped.append(student.student_code)
            continue
        db.refresh(enrollment)
        added.append(_serialize_session_enrollment(db, enrollment))

    enrolled = [_serialize_session_enrollment(db, item) for item in _session_enrollment_query(db, session_id).all()]
    return added, skipped, enrolled


@router.post("/sessions/{session_id}/enroll")
def enroll_students_in_session(
    session_id: int,
    data: SessionEnrollmentRequest,
    request: Request = None,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_session_or_404(db, session_id)

    requested_codes = []
    seen_codes = set()
    for code in data.student_codes:
        normalized_code = code.strip()
        if not normalized_code or normalized_code in seen_codes:
            continue
        seen_codes.add(normalized_code)
        requested_codes.append(normalized_code)

    if not requested_codes:
        raise HTTPException(status_code=400, detail="Danh sách sinh viên không được rỗng.")

    students = db.query(Student).filter(Student.student_code.in_(requested_codes)).all()
    by_code = {student.student_code: student for student in students}
    failed = [
        {"student_code": code, "reason": "Không tìm thấy sinh viên."}
        for code in requested_codes
        if code not in by_code
    ]

    added, skipped, enrolled = _add_students_to_session_enrollment(
        db,
        session_id,
        [by_code[code] for code in requested_codes if code in by_code],
    )
    audit_safely(
        db,
        action="session_enrollment_updated",
        actor_user=_current_user,
        target_type="session",
        target_id=session_id,
        details=audit_details(
            request=request,
            new_value={"added": added, "skipped_student_codes": skipped, "failed_items": failed},
            requested_student_codes=requested_codes,
        ),
    )

    return {
        "session_id": session_id,
        "requested": len(requested_codes),
        "added": len(added),
        "skipped": len(skipped),
        "failed": len(failed),
        "skipped_student_codes": skipped,
        "failed_items": failed,
        "enrolled": enrolled,
    }


@router.get("/sessions/{session_id}/enrollments")
def get_session_enrollments(session_id: int, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    _get_session_or_404(db, session_id)
    return [_serialize_session_enrollment(db, enrollment) for enrollment in _session_enrollment_query(db, session_id).all()]


@router.delete("/sessions/{session_id}/enroll/{student_code}")
def delete_session_enrollment(
    session_id: int,
    student_code: str,
    request: Request = None,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_session_or_404(db, session_id)
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")

    enrollment = (
        db.query(Enrollment)
        .filter(Enrollment.session_id == session_id, Enrollment.student_id == student.id)
        .first()
    )
    if not enrollment:
        raise HTTPException(status_code=404, detail="Sinh viên chưa có trong enrollment của buổi học.")

    old_value = model_snapshot(enrollment, ENROLLMENT_AUDIT_FIELDS)
    db.delete(enrollment)
    db.commit()
    audit_safely(
        db,
        action="session_enrollment_deleted",
        actor_user=_current_user,
        target_type="session_enrollment",
        target_id=f"{session_id}:{student.id}",
        details=audit_details(request=request, old_value=old_value, student_code=student.student_code),
    )
    return {
        "session_id": session_id,
        "student_code": student.student_code,
        "message": "Đã xóa sinh viên khỏi enrollment của buổi học.",
    }


@router.post("/sessions/{session_id}/enroll/import")
def import_session_enrollments_by_class(
    session_id: int,
    data: SessionEnrollmentImportRequest,
    request: Request = None,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    _get_session_or_404(db, session_id)
    class_name = data.class_name.strip()
    if not class_name:
        raise HTTPException(status_code=400, detail="class_name không được rỗng.")

    students = db.query(Student).filter(Student.class_name == class_name).order_by(Student.student_code.asc()).all()
    added, skipped, enrolled = _add_students_to_session_enrollment(db, session_id, students)
    audit_safely(
        db,
        action="session_enrollment_imported",
        actor_user=_current_user,
        target_type="session",
        target_id=session_id,
        details=audit_details(
            request=request,
            new_value={"added": added, "skipped_student_codes": skipped},
            class_name=class_name,
            total_found=len(students),
        ),
    )

    return {
        "session_id": session_id,
        "class_name": class_name,
        "total_found": len(students),
        "added": len(added),
        "skipped": len(skipped),
        "skipped_student_codes": skipped,
        "enrolled": enrolled,
    }


@router.post("/enrollments")
def create_enrollment(
    data: EnrollmentCreate,
    request: Request = None,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
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
    audit_safely(
        db,
        action="enrollment_created",
        actor_user=_current_user,
        target_type="enrollment",
        target_id=enrollment.id,
        details=audit_details(request=request, new_value=model_snapshot(enrollment, ENROLLMENT_AUDIT_FIELDS)),
    )
    return _serialize_enrollment(db, enrollment)


@router.delete("/enrollments/{enrollment_id}")
def delete_enrollment(
    enrollment_id: int,
    request: Request = None,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    enrollment = db.query(Enrollment).filter(Enrollment.id == enrollment_id).first()
    if not enrollment:
        raise HTTPException(status_code=404, detail="Không tìm thấy đăng ký học phần.")
    old_value = model_snapshot(enrollment, ENROLLMENT_AUDIT_FIELDS)
    db.delete(enrollment)
    db.commit()
    audit_safely(
        db,
        action="enrollment_deleted",
        actor_user=_current_user,
        target_type="enrollment",
        target_id=enrollment_id,
        details=audit_details(request=request, old_value=old_value),
    )
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
