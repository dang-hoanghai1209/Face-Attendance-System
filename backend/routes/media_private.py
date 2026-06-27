from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import or_
from sqlalchemy.orm import Session

from database import get_db
from models.course_section import CourseSection
from models.security_alert import SecurityAlert
from models.session import Session as ClassSession
from services.auth_service import get_current_user


BASE_DIR = Path(__file__).resolve().parents[1]
MEDIA_ROOT = (BASE_DIR / "media").resolve()
PRIVATE_MEDIA_ROOT = (BASE_DIR / "private_media").resolve()
ALLOWED_IMAGE_MEDIA_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}

router = APIRouter(prefix="/media-private", tags=["Private Media"])


def _identity_values(user):
    values = {getattr(user, "username", None), getattr(user, "full_name", None)}
    return [value for value in values if value]


def _teacher_can_access_session(db: Session, user, session_id: int) -> bool:
    identities = _identity_values(user)
    if not identities:
        return False
    return (
        db.query(ClassSession.id)
        .outerjoin(CourseSection, ClassSession.section_id == CourseSection.id)
        .filter(
            ClassSession.id == session_id,
            or_(
                ClassSession.created_by.in_(identities),
                CourseSection.lecturer_name.in_(identities),
            ),
        )
        .first()
        is not None
    )


def _require_alert_image_access(db: Session, user, alert: SecurityAlert) -> None:
    role = getattr(user, "role", None)
    if role == "admin":
        return
    if role == "teacher" and _teacher_can_access_session(db, user, alert.session_id):
        return
    raise HTTPException(status_code=403, detail="Bạn không có quyền xem ảnh cảnh báo này.")


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _resolve_private_media_path(raw_path: str | None) -> Path:
    if not raw_path:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh cảnh báo.")

    path = Path(raw_path)
    if path.is_absolute() or ".." in path.parts:
        raise HTTPException(status_code=403, detail="Đường dẫn ảnh không hợp lệ.")

    resolved = (BASE_DIR / path).resolve()
    if not (_is_relative_to(resolved, MEDIA_ROOT) or _is_relative_to(resolved, PRIVATE_MEDIA_ROOT)):
        raise HTTPException(status_code=403, detail="Đường dẫn ảnh không hợp lệ.")
    if not resolved.is_file():
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh cảnh báo.")
    return resolved


@router.get("/alerts/{alert_id}/image")
def get_alert_image(alert_id: int, current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    alert = db.query(SecurityAlert).filter(SecurityAlert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="Không tìm thấy cảnh báo bảo mật.")
    if not alert.captured_img:
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh cảnh báo.")

    _require_alert_image_access(db, current_user, alert)
    image_path = _resolve_private_media_path(alert.captured_img)
    media_type = ALLOWED_IMAGE_MEDIA_TYPES.get(image_path.suffix.lower())
    return FileResponse(
        image_path,
        media_type=media_type,
        headers={"Cache-Control": "private, no-store"},
    )
