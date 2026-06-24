from datetime import datetime

from sqlalchemy import Boolean, CheckConstraint, Column, DateTime, Integer, String

from database import Base


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("role IN ('admin', 'teacher', 'student')", name="ck_users_role"),
    )

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(80), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    full_name = Column(String(120), nullable=True)
    role = Column(String(20), nullable=False, default="teacher")
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
