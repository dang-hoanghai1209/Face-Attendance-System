from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


ATTENDANCE_STATUSES = {"present", "late", "manual", "left_early"}


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
    gps_lat = Column(Float)
    gps_lng = Column(Float)
    gps_accuracy = Column(Float)
    distance_meters = Column(Float)
    liveness_passed = Column(Boolean, nullable=True, default=False)
    status = Column(String(20), default="present")
    scan_count = Column(Integer, nullable=False, default=0)
    last_scan_at = Column(DateTime)
    note = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
