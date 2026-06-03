import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String

from database import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    student_code = Column(String(8), unique=True, index=True, nullable=False)
    full_name = Column(String(100), nullable=False)
    class_name = Column(String(10))
    face_status = Column(String(20), default="unregistered")
    data_source = Column(String(20), default="real", nullable=False)
    registration_method = Column(String(20), nullable=True)
    is_demo = Column(Boolean, default=False, nullable=False)
    avatar_path = Column(String(255))
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
