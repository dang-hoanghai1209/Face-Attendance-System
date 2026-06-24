from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database import get_db
from models.audit_log import AuditLog
from models.user import User
from services.audit_service import audit_safely
from services.auth_service import (
    create_access_token,
    ensure_active_role,
    get_current_user,
    hash_password,
    require_admin,
    resolve_student_for_user,
    verify_password,
)


router = APIRouter(prefix="/auth", tags=["Auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserCreateRequest(BaseModel):
    username: str
    password: str
    full_name: Optional[str] = None
    role: str = "teacher"
    is_active: bool = True


class UserUpdateRequest(BaseModel):
    username: Optional[str] = None
    password: Optional[str] = None
    full_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


def serialize_user(user: User, db: Session):
    student = resolve_student_for_user(db, user)
    return {
        "id": user.id,
        "username": user.username,
        "full_name": student.full_name if student else user.full_name,
        "role": user.role,
        "is_active": user.is_active,
        "student_id": student.id if student else None,
        "student_code": student.student_code if student else None,
    }


@router.post("/login")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    username = payload.username.strip()
    user = db.query(User).filter(User.username == username).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        audit_safely(db, action="login_failed", actor_username=username, target_type="user", target_id=username)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid username or password.",
        )

    audit_safely(db, action="login_success", actor_user=user, target_type="user", target_id=user.id)
    return {
        "access_token": create_access_token(user),
        "token_type": "bearer",
        "user": serialize_user(user, db),
    }


@router.get("/me")
def get_me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    return serialize_user(current_user, db)


@router.get("/users")
def list_users(_current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    return [serialize_user(user, db) for user in db.query(User).order_by(User.username.asc()).all()]


@router.get("/audit-logs")
def list_audit_logs(_current_user: User = Depends(require_admin), db: Session = Depends(get_db)):
    logs = db.query(AuditLog).order_by(AuditLog.created_at.desc()).limit(200).all()
    return [
        {
            "id": log.id,
            "actor_user_id": log.actor_user_id,
            "actor_username": log.actor_username,
            "actor_role": log.actor_role,
            "action": log.action,
            "target_type": log.target_type,
            "target_id": log.target_id,
            "details": log.details,
            "created_at": log.created_at.isoformat() if log.created_at else None,
        }
        for log in logs
    ]


@router.post("/users", status_code=status.HTTP_201_CREATED)
def create_user(
    payload: UserCreateRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    username = payload.username.strip()
    if not username:
        raise HTTPException(status_code=400, detail="Username is required.")
    if len(payload.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
    role = ensure_active_role(payload.role)
    if db.query(User).filter(User.username == username).first():
        raise HTTPException(status_code=400, detail="Username already exists.")

    user = User(
        username=username,
        password_hash=hash_password(payload.password),
        full_name=payload.full_name,
        role=role,
        is_active=payload.is_active,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    audit_safely(
        db,
        action="user_created",
        actor_user=_current_user,
        target_type="user",
        target_id=user.id,
        details={"username": user.username, "role": user.role, "is_active": user.is_active},
    )
    return serialize_user(user, db)


@router.put("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    _current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found.")

    changed_fields = []
    updates = payload.model_dump(exclude_unset=True)
    if "username" in updates:
        username = (updates["username"] or "").strip()
        if not username:
            raise HTTPException(status_code=400, detail="Username is required.")
        duplicate = db.query(User).filter(User.username == username, User.id != user_id).first()
        if duplicate:
            raise HTTPException(status_code=400, detail="Username already exists.")
        user.username = username
        changed_fields.append("username")
    if "password" in updates:
        password = updates["password"] or ""
        if len(password) < 8:
            raise HTTPException(status_code=400, detail="Password must be at least 8 characters.")
        user.password_hash = hash_password(password)
        changed_fields.append("password")
    if "full_name" in updates:
        user.full_name = updates["full_name"]
        changed_fields.append("full_name")
    if "role" in updates:
        user.role = ensure_active_role(updates["role"])
        changed_fields.append("role")
    if "is_active" in updates:
        user.is_active = updates["is_active"]
        changed_fields.append("is_active")

    db.commit()
    db.refresh(user)
    audit_safely(
        db,
        action="user_updated",
        actor_user=_current_user,
        target_type="user",
        target_id=user.id,
        details={"changed_fields": changed_fields, "role": user.role, "is_active": user.is_active},
    )
    return serialize_user(user, db)
