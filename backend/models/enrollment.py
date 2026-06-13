from sqlalchemy import Column, DateTime, ForeignKey, Index, Integer, String, Text, UniqueConstraint
from sqlalchemy.sql import func

from database import Base


class Enrollment(Base):
    __tablename__ = "enrollments"
    __table_args__ = (
        UniqueConstraint("session_id", "student_id", name="uq_enrollments_session_student"),
        UniqueConstraint("course_section_id", "student_id", name="uq_enrollments_section_student"),
        Index("ix_enrollments_session_id", "session_id"),
    )

    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=True)
    course_section_id = Column(Integer, ForeignKey("course_sections.id"), nullable=True, index=True)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False, index=True)
    enrolled_at = Column(DateTime, server_default=func.now())
    note = Column(Text)
    status = Column(String(20), nullable=False, default="active")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
