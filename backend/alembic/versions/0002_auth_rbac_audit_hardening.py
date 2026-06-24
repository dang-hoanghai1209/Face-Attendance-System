"""auth rbac audit hardening

Revision ID: 0002_auth_rbac_audit_hardening
Revises: 0001_current_schema_with_audit
Create Date: 2026-06-24
"""
from alembic import op
from sqlalchemy import inspect, text

from database import Base
from models.audit_log import AuditLog  # noqa: F401
from models.user import User  # noqa: F401


revision = "0002_auth_rbac_audit_hardening"
down_revision = "0001_current_schema_with_audit"
branch_labels = None
depends_on = None


def _create_model_table_if_missing(table_name: str) -> None:
    bind = op.get_bind()
    if table_name not in inspect(bind).get_table_names():
        Base.metadata.tables[table_name].create(bind=bind, checkfirst=True)


def _normalize_user_roles() -> None:
    bind = op.get_bind()
    inspector = inspect(bind)
    if "users" not in inspector.get_table_names():
        return

    columns = {column["name"] for column in inspector.get_columns("users")}
    if "role" not in columns:
        return

    op.execute(text("UPDATE users SET role = 'teacher' WHERE role IS NULL OR role = ''"))
    op.execute(text("UPDATE users SET role = 'teacher' WHERE role IN ('lecturer', 'viewer')"))

    if bind.dialect.name == "postgresql":
        op.execute(
            text(
                """
                DO $$
                BEGIN
                    ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;
                    ALTER TABLE users
                    ADD CONSTRAINT ck_users_role CHECK (role IN ('admin', 'teacher', 'student'));
                END $$;
                """
            )
        )


def upgrade():
    _create_model_table_if_missing("users")
    _create_model_table_if_missing("audit_logs")
    _normalize_user_roles()


def downgrade():
    # Intentionally non-destructive: keep users and audit history.
    pass
