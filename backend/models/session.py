from sqlalchemy import Column, Date, DateTime, Float, ForeignKey, Integer, String, Text, Time
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database import Base
from models.classroom import Classroom  # noqa: F401
from models.course_section import CourseSection  # noqa: F401

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(100))
    class_name = Column(String(50))
    section_group = Column(String(30), nullable=True)
    section_id = Column(Integer, ForeignKey("course_sections.id"), nullable=True, index=True)

    section = relationship("CourseSection", foreign_keys=[section_id])
    classroom_id = Column(Integer, ForeignKey("classrooms.id"), nullable=True, index=True)
    latitude = Column(Float)
    longitude = Column(Float)
    radius_meters = Column(Integer, default=50)
    room_name = Column(String(100))
    session_date = Column(Date, nullable=False)
    start_time = Column(Time)
    end_time = Column(Time)
    session_number = Column(Integer, nullable=True)
    note = Column(Text)
    created_by = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
