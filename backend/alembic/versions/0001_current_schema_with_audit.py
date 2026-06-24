"""current schema with audit log

Revision ID: 0001_current_schema_with_audit
Revises:
Create Date: 2026-06-24
"""
from alembic import op

from database import Base
from models.attendance import Attendance  # noqa: F401
from models.attendance_scan import AttendanceScan  # noqa: F401
from models.audit_log import AuditLog  # noqa: F401
from models.classroom import Classroom  # noqa: F401
from models.course_section import CourseSection  # noqa: F401
from models.enrollment import Enrollment  # noqa: F401
from models.face_embedding import FaceEmbedding  # noqa: F401
from models.recognition_attempt import RecognitionAttempt  # noqa: F401
from models.security_alert import SecurityAlert  # noqa: F401
from models.session import Session  # noqa: F401
from models.student import Student  # noqa: F401
from models.subject import Subject  # noqa: F401
from models.user import User  # noqa: F401


revision = "0001_current_schema_with_audit"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade():
    op.drop_table("audit_logs")
