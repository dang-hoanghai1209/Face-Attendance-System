from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.course_section import CourseSection
from models.subject import Subject
from services.auth_service import get_current_user, require_admin


router = APIRouter(prefix="/subjects", tags=["Subjects"])


class SubjectCreate(BaseModel):
    subject_code: str
    subject_name: str
    credits: Optional[int] = None
    department: Optional[str] = None

    @field_validator("subject_code", "subject_name")
    @classmethod
    def validate_required_text(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Vui lòng nhập đầy đủ thông tin học phần.")
        return value


class SubjectUpdate(BaseModel):
    subject_code: Optional[str] = None
    subject_name: Optional[str] = None
    credits: Optional[int] = None
    department: Optional[str] = None

    @field_validator("subject_code", "subject_name")
    @classmethod
    def validate_text(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Thông tin học phần không được để trống.")
        return value


@router.get("/")
def get_subjects(_current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Subject).order_by(Subject.subject_code.asc()).all()


@router.post("/")
def create_subject(data: SubjectCreate, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    subject = Subject(**data.model_dump())
    db.add(subject)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Mã học phần đã tồn tại.") from exc
    db.refresh(subject)
    return subject


@router.put("/{subject_id}")
def update_subject(subject_id: int, data: SubjectUpdate, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Không tìm thấy học phần.")
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(subject, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Mã học phần đã tồn tại.") from exc
    db.refresh(subject)
    return subject


@router.delete("/{subject_id}")
def delete_subject(subject_id: int, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    subject = db.query(Subject).filter(Subject.id == subject_id).first()
    if not subject:
        raise HTTPException(status_code=404, detail="Không tìm thấy học phần.")
    used = db.query(CourseSection).filter(CourseSection.subject_id == subject_id).first()
    if used:
        raise HTTPException(status_code=400, detail="Không thể xóa học phần đang có lớp học phần.")
    db.delete(subject)
    db.commit()
    return {"message": "Đã xóa học phần."}
