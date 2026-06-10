from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.classroom import Classroom
from models.session import Session as ClassSession
from services.auth_service import get_current_user, require_admin


router = APIRouter(prefix="/classrooms", tags=["Classrooms"])


class ClassroomCreate(BaseModel):
    name: str
    building: Optional[str] = None
    gps_lat: float
    gps_lng: float
    radius_meters: float
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Vui lòng nhập tên phòng học.")
        return value

    @field_validator("radius_meters")
    @classmethod
    def validate_radius(cls, value):
        if value <= 0:
            raise ValueError("Bán kính điểm danh phải lớn hơn 0 mét.")
        return value


class ClassroomUpdate(BaseModel):
    name: Optional[str] = None
    building: Optional[str] = None
    gps_lat: Optional[float] = None
    gps_lng: Optional[float] = None
    radius_meters: Optional[float] = None
    is_active: Optional[bool] = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value):
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Vui lòng nhập tên phòng học.")
        return value

    @field_validator("radius_meters")
    @classmethod
    def validate_radius(cls, value):
        if value is not None and value <= 0:
            raise ValueError("Bán kính điểm danh phải lớn hơn 0 mét.")
        return value


@router.get("/")
def get_classrooms(_current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    return db.query(Classroom).order_by(Classroom.name.asc()).all()


@router.post("/")
def create_classroom(data: ClassroomCreate, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    classroom = Classroom(**data.model_dump())
    db.add(classroom)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tên phòng học đã tồn tại.") from exc
    db.refresh(classroom)
    return classroom


@router.put("/{classroom_id}")
def update_classroom(
    classroom_id: int,
    data: ClassroomUpdate,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng học.")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(classroom, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tên phòng học đã tồn tại.") from exc
    db.refresh(classroom)
    return classroom


@router.delete("/{classroom_id}")
def delete_classroom(classroom_id: int, _current_user=Depends(require_admin), db: Session = Depends(get_db)):
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng học.")
    used = db.query(ClassSession).filter(ClassSession.classroom_id == classroom_id).first()
    if used:
        raise HTTPException(status_code=400, detail="Không thể xóa phòng học đang được gắn với buổi học.")
    db.delete(classroom)
    db.commit()
    return {"message": "Đã xóa phòng học."}
