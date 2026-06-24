import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import engine_from_config, pool

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


config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

load_dotenv()
database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is required to run Alembic migrations.")
config.set_main_option("sqlalchemy.url", database_url)

target_metadata = Base.metadata


def run_migrations_offline():
    context.configure(
        url=database_url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
