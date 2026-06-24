from typing import Any

from sqlalchemy.orm import Session

from models.audit_log import AuditLog


def create_audit_log(
    db: Session,
    *,
    action: str,
    actor_user=None,
    actor_username: str | None = None,
    actor_role: str | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    details: dict[str, Any] | None = None,
):
    log = AuditLog(
        actor_user_id=getattr(actor_user, "id", None),
        actor_username=actor_username or getattr(actor_user, "username", None),
        actor_role=actor_role or getattr(actor_user, "role", None),
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        details=details,
    )
    db.add(log)
    db.commit()
    db.refresh(log)
    return log


def audit_safely(db: Session, **kwargs):
    try:
        return create_audit_log(db, **kwargs)
    except Exception:
        db.rollback()
        return None
