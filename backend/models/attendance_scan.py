from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, Text

from database import Base
from services.timezone_service import now_in_app_timezone


class AttendanceScan(Base):
    __tablename__ = "attendance_scans"

    id = Column(Integer, primary_key=True, index=True)
    attendance_id = Column(Integer, ForeignKey("attendance.id"), nullable=False, index=True)
    scanned_at = Column(DateTime, default=now_in_app_timezone, index=True)
    confidence = Column(Float)
    gps_lat = Column(Float)
    gps_lng = Column(Float)
    liveness_passed = Column(Boolean, nullable=True)
    scan_index = Column(Integer)
    note = Column(Text)
