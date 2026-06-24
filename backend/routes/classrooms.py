from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, field_validator
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from database import get_db
from models.classroom import Classroom
from models.session import Session as ClassSession
from services.audit_service import audit_details, audit_safely, model_snapshot
from services.auth_service import get_current_user, require_admin


router = APIRouter(prefix="/classrooms", tags=["Classrooms"])
CLASSROOM_AUDIT_FIELDS = ("name", "building", "gps_lat", "gps_lng", "radius_meters", "is_active")


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
def create_classroom(
    data: ClassroomCreate,
    request: Request = None,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    classroom = Classroom(**data.model_dump())
    db.add(classroom)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tên phòng học đã tồn tại.") from exc
    db.refresh(classroom)
    audit_safely(
        db,
        action="classroom_created",
        actor_user=_current_user,
        target_type="classroom",
        target_id=classroom.id,
        details=audit_details(request=request, new_value=model_snapshot(classroom, CLASSROOM_AUDIT_FIELDS)),
    )
    return classroom


@router.put("/{classroom_id}")
def update_classroom(
    classroom_id: int,
    data: ClassroomUpdate,
    request: Request = None,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng học.")

    old_value = model_snapshot(classroom, CLASSROOM_AUDIT_FIELDS)
    updates = data.model_dump(exclude_unset=True)
    for field, value in updates.items():
        setattr(classroom, field, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=400, detail="Tên phòng học đã tồn tại.") from exc
    db.refresh(classroom)
    audit_safely(
        db,
        action="classroom_updated",
        actor_user=_current_user,
        target_type="classroom",
        target_id=classroom.id,
        details=audit_details(
            request=request,
            old_value=old_value,
            new_value=model_snapshot(classroom, CLASSROOM_AUDIT_FIELDS),
            changed_fields=sorted(updates.keys()),
        ),
    )
    return classroom


@router.delete("/{classroom_id}")
def delete_classroom(
    classroom_id: int,
    request: Request = None,
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    classroom = db.query(Classroom).filter(Classroom.id == classroom_id).first()
    if not classroom:
        raise HTTPException(status_code=404, detail="Không tìm thấy phòng học.")
    used = db.query(ClassSession).filter(ClassSession.classroom_id == classroom_id).first()
    if used:
        raise HTTPException(status_code=400, detail="Không thể xóa phòng học đang được gắn với buổi học.")
    old_value = model_snapshot(classroom, CLASSROOM_AUDIT_FIELDS)
    db.delete(classroom)
    db.commit()
    audit_safely(
        db,
        action="classroom_deleted",
        actor_user=_current_user,
        target_type="classroom",
        target_id=classroom_id,
        details=audit_details(request=request, old_value=old_value),
    )
    return {"message": "Đã xóa phòng học."}
