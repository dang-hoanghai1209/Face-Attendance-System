from datetime import date, datetime, time
from typing import Any

from sqlalchemy.orm import Session

from models.audit_log import AuditLog


def _json_safe(value: Any):
    if isinstance(value, (datetime, date, time)):
        return value.isoformat()
    return value


def model_snapshot(obj, fields: list[str] | tuple[str, ...]):
    if obj is None:
        return None
    return {field: _json_safe(getattr(obj, field, None)) for field in fields}


def request_metadata(request=None):
    if request is None:
        return {}
    return {
        "ip_address": request.client.host if request.client else None,
        "user_agent": request.headers.get("user-agent"),
    }


def audit_details(
    *,
    old_value: dict[str, Any] | None = None,
    new_value: dict[str, Any] | None = None,
    request=None,
    **extra,
):
    details = {key: _json_safe(value) for key, value in extra.items() if value is not None}
    if old_value is not None:
        details["old_value"] = old_value
    if new_value is not None:
        details["new_value"] = new_value
    details.update({key: value for key, value in request_metadata(request).items() if value is not None})
    return details or None


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
