from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text

from database import Base
from services.timezone_service import now_in_app_timezone


class RecognitionAttempt(Base):
    __tablename__ = "recognition_attempts"

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True, index=True)
    predicted_student_id = Column(Integer, ForeignKey("students.id"), nullable=True, index=True)
    predicted_student_code = Column(String(8), nullable=True, index=True)
    confidence = Column(Float)
    status = Column(String(20), nullable=False, index=True)
    image_path = Column(String(255))
    message = Column(Text)
    created_at = Column(DateTime, default=now_in_app_timezone, index=True)
