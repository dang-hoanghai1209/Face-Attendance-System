from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.sql import func

from database import Base


class SecurityAlert(Base):
    __tablename__ = "security_alerts"
    __table_args__ = (
        Index("ix_security_alerts_session_dismissed", "session_id", "dismissed"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    alert_type = Column(String(20), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    captured_img = Column(String(255), nullable=True)
    confidence = Column(Float, nullable=True)
    liveness_score = Column(Float, nullable=True)
    gps_lat = Column(Float, nullable=True)
    gps_lng = Column(Float, nullable=True)
    dismissed = Column(Boolean, nullable=False, default=False, server_default=text("false"))
    dismissed_by = Column(String(80), nullable=True)
    dismissed_at = Column(DateTime, nullable=True)
    note = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
