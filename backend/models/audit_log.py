from sqlalchemy import Column, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.sql import func

from database import Base


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    actor_username = Column(String(80), nullable=True, index=True)
    actor_role = Column(String(20), nullable=True)
    action = Column(String(80), nullable=False, index=True)
    target_type = Column(String(80), nullable=True, index=True)
    target_id = Column(String(80), nullable=True, index=True)
    details = Column(JSON, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
