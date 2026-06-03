from sqlalchemy import Column, Date, DateTime, Integer, String, Time
from sqlalchemy.sql import func

from database import Base

class Session(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, index=True)
    subject = Column(String(100))
    class_name = Column(String(50))
    session_date = Column(Date, nullable=False)
    start_time = Column(Time)
    end_time = Column(Time)
    created_by = Column(String(50))
    created_at = Column(DateTime, server_default=func.now())
