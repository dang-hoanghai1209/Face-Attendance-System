from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.sql import func

from database import Base
from models.subject import Subject  # noqa: F401
from models.user import User  # noqa: F401


class CourseSection(Base):
    __tablename__ = "course_sections"

    id = Column(Integer, primary_key=True, index=True)
    section_code = Column(String(80), nullable=False, unique=True, index=True)
    class_name = Column(String(50), nullable=True)
    section_group = Column(String(30), nullable=True)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False, index=True)
    semester = Column(String(30))
    academic_year = Column(String(30))
    lecturer_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    lecturer_name = Column(String(120))
    min_students = Column(Integer)
    max_students = Column(Integer)
    status = Column(String(20), nullable=False, default="open")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
