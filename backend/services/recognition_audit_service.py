from pathlib import Path
from uuid import uuid4

from models.recognition_attempt import RecognitionAttempt
from models.student import Student
from services.timezone_service import now_in_app_timezone


BASE_DIR = Path(__file__).resolve().parents[1]
MEDIA_ROOT = BASE_DIR / "media" / "recognition_attempts"


def save_recognition_capture(image_data: bytes, original_filename=None):
    if not image_data:
        return None

    now = now_in_app_timezone()
    relative_dir = Path("media") / "recognition_attempts" / now.strftime("%Y%m%d")
    output_dir = BASE_DIR / relative_dir
    output_dir.mkdir(parents=True, exist_ok=True)

    suffix = Path(original_filename or "").suffix.lower()
    if suffix not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        suffix = ".jpg"

    filename = f"{now.strftime('%H%M%S')}_{uuid4().hex}{suffix}"
    output_path = output_dir / filename
    output_path.write_bytes(image_data)
    return str(relative_dir / filename).replace("\\", "/")


def create_recognition_attempt(
    db,
    *,
    session_id=None,
    predicted_student_code=None,
    confidence=None,
    status,
    image_path=None,
    message=None,
):
    predicted_student_id = None
    if predicted_student_code:
        student = db.query(Student).filter(Student.student_code == predicted_student_code).first()
        predicted_student_id = student.id if student else None

    attempt = RecognitionAttempt(
        session_id=session_id,
        predicted_student_id=predicted_student_id,
        predicted_student_code=predicted_student_code,
        confidence=confidence,
        status=status,
        image_path=image_path,
        message=message,
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)
    return attempt
