from sqlalchemy import Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from database import Base

class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (
        UniqueConstraint("student_id", "session_id", name="uq_attendance_student_session"),
    )

    id = Column(Integer, primary_key=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"))
    session_id = Column(Integer, ForeignKey("sessions.id"))
    check_in_at = Column(DateTime, server_default=func.now())
    check_out_at = Column(DateTime)
    check_in_conf = Column(Float)
    check_out_conf = Column(Float)
    check_in_img = Column(String(255))
    status = Column(String(20), default="present")
    note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
