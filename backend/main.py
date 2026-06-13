import os
import csv
import logging
from pathlib import Path
from time import perf_counter
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from PIL import UnidentifiedImageError
import uvicorn

from database import Base, SessionLocal, engine
from face_service import (
    ENABLE_LEGACY_EMBEDDINGS,
    THRESHOLD_CONFIRM,
    THRESHOLD_UNCERTAIN,
    check_liveness,
    device,
    count_faces_in_image_bytes,
    face_models_loaded,
    fetch_db_embeddings,
    image_bytes_to_face_embeddings,
    image_bytes_to_embedding,
    load_legacy_embeddings,
    match_embedding,
)
from models.recognition_attempt import RecognitionAttempt  # noqa: F401
from models.attendance_scan import AttendanceScan  # noqa: F401
from models.classroom import Classroom  # noqa: F401
from models.course_section import CourseSection  # noqa: F401
from models.enrollment import Enrollment  # noqa: F401
from models.session import Session as ClassSession
from models.security_alert import SecurityAlert  # noqa: F401
from models.student import Student
from models.subject import Subject  # noqa: F401
from models.user import User  # noqa: F401
from schema_sync import sync_schema
from routes import alerts, attendance, auth, classrooms, course_sections, enrollments, faces, reports, sessions, students, subjects
from services.auth_service import bootstrap_admin_user, get_current_user, require_admin
from services.recognition_audit_service import create_recognition_attempt, save_recognition_capture
from services.attendance_service import (
    CROSS_CLASS_REASON_CODE,
    OFFICIAL_ATTENDANCE_BLOCK_MESSAGE,
    cross_class_attendance_message,
)
from services.timezone_service import configured_timezone_name, resolved_timezone_name


app = FastAPI(title="Face Attendance System")
logger = logging.getLogger("face_attendance")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(BASE_DIR, "data", "embedding_db.pkl")
MODEL_TEST_LOG_PATH = Path(BASE_DIR) / "reports" / "model_test_log.csv"
MEDIA_DIR = Path(BASE_DIR) / "media"
MEDIA_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/media", StaticFiles(directory=MEDIA_DIR), name="media")

legacy_embeddings = {}


@app.on_event("startup")
async def startup_event():
    global legacy_embeddings

    Base.metadata.create_all(bind=engine)
    sync_schema(engine)
    db = SessionLocal()
    try:
        bootstrap_admin_user(db)
    finally:
        db.close()
    legacy_embeddings = load_legacy_embeddings(DB_PATH) if ENABLE_LEGACY_EMBEDDINGS else {}


@app.get("/")
def read_root():
    return {"status": "online", "message": "Máy chủ hệ thống điểm danh khuôn mặt đã sẵn sàng."}


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "legacy_embeddings_enabled": ENABLE_LEGACY_EMBEDDINGS,
        "legacy_embeddings_loaded": len(legacy_embeddings),
        "threshold_confirm": THRESHOLD_CONFIRM,
        "threshold_uncertain": THRESHOLD_UNCERTAIN,
        "device": str(device),
        "face_models_loaded": face_models_loaded(),
        "timezone": configured_timezone_name(),
        "resolved_timezone": resolved_timezone_name(),
    }


def _save_capture_safely(image_data: bytes, filename: str | None):
    try:
        return save_recognition_capture(image_data, filename)
    except Exception:
        return None


def _audit_recognition_safely(
    db,
    *,
    session_id=None,
    predicted_student_code=None,
    confidence=None,
    status,
    image_path=None,
    message=None,
):
    try:
        return create_recognition_attempt(
            db,
            session_id=session_id,
            predicted_student_code=predicted_student_code,
            confidence=confidence,
            status=status,
            image_path=image_path,
            message=message,
        )
    except Exception:
        db.rollback()
        return None


def _serialize_student(student: Student | None):
    if not student:
        return None

    return {
        "id": student.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "class_name": student.class_name,
        "face_status": student.face_status,
        "data_source": student.data_source,
        "registration_method": student.registration_method,
        "is_demo": student.is_demo,
        "avatar_path": student.avatar_path,
        "created_at": student.created_at.isoformat() if student.created_at else None,
    }


def _official_attendance_warning(student: Student | None):
    if not student:
        return None
    if student.data_source != "real" or student.is_demo:
        return OFFICIAL_ATTENDANCE_BLOCK_MESSAGE
    if student.face_status != "registered":
        return "Sinh viên chưa đăng ký khuôn mặt, không được ghi nhận điểm danh chính thức."
    return None


def _session_membership_warning(student_data: dict | None, session: ClassSession | None):
    if not student_data or not session:
        return None, None
    if student_data.get("class_name") != session.class_name:
        return cross_class_attendance_message(student_data.get("class_name"), session.class_name), CROSS_CLASS_REASON_CODE
    return None, None


def _append_model_test_log(result):
    MODEL_TEST_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "status",
        "student_code",
        "full_name",
        "data_source",
        "is_demo",
        "registration_method",
        "confidence",
        "processing_time_ms",
    ]
    write_header = not MODEL_TEST_LOG_PATH.exists()
    with MODEL_TEST_LOG_PATH.open("a", newline="", encoding="utf-8") as log_file:
        writer = csv.DictWriter(log_file, fieldnames=fieldnames)
        if write_header:
            writer.writeheader()
        writer.writerow({field: result.get(field) for field in fieldnames})


@app.post("/recognize")
def recognize_face(
    file: UploadFile = File(...),
    session_id: int = Form(...),
    current_user: User = Depends(get_current_user),
):
    logger.info(
        "recognize request received: session_id=%s filename=%s user=%s role=%s",
        session_id,
        file.filename,
        current_user.username,
        current_user.role,
    )
    try:
        result = _recognize_uploaded_face(
            file=file,
            session_id=session_id,
            official_mode=True,
            save_capture=True,
            audit_recognition=True,
        )
        logger.info(
            "recognize request completed: session_id=%s status=%s student_code=%s confidence=%s",
            session_id,
            result.get("status"),
            result.get("student_code"),
            result.get("confidence"),
        )
        return result
    except HTTPException:
        logger.info("recognize request failed: session_id=%s filename=%s", session_id, file.filename, exc_info=True)
        raise
    except Exception as exc:
        logger.exception("recognize request crashed: session_id=%s filename=%s", session_id, file.filename)
        raise HTTPException(status_code=500, detail="Máy chủ không thể hoàn tất quá trình nhận diện khuôn mặt.") from exc


@app.post("/recognize/model-test")
def recognize_face_for_model_test(
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
):
    result = _recognize_uploaded_face(
        file=file,
        session_id=None,
        official_mode=False,
        reject_multiple_faces=True,
        save_capture=False,
        audit_recognition=False,
    )
    _append_model_test_log(result)
    return result


def _recognize_uploaded_face(
    *,
    file: UploadFile,
    session_id: Optional[int] = None,
    official_mode: bool = True,
    reject_multiple_faces: bool = False,
    save_capture: bool = True,
    audit_recognition: bool = True,
):
    return _recognize_uploaded_face_multi(
        file=file,
        session_id=session_id,
        official_mode=official_mode,
        reject_multiple_faces=reject_multiple_faces,
        save_capture=save_capture,
        audit_recognition=audit_recognition,
    )


def _recognize_uploaded_face_multi(
    *,
    file: UploadFile,
    session_id: Optional[int] = None,
    official_mode: bool = True,
    reject_multiple_faces: bool = False,
    save_capture: bool = True,
    audit_recognition: bool = True,
):
    started_at = perf_counter()
    image_data = file.file.read()
    if not image_data:
        raise HTTPException(status_code=400, detail="Không đọc được ảnh: file tải lên rỗng.")
    capture_path = _save_capture_safely(image_data, file.filename) if save_capture else None

    session = None
    if official_mode:
        if session_id is None:
            raise HTTPException(status_code=400, detail="Thiếu session_id cho luồng điểm danh.")
        db = SessionLocal()
        try:
            session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
            if not session:
                raise HTTPException(status_code=404, detail=f"Không tìm thấy buổi học #{session_id}.")
            session.id
            session.class_name
        finally:
            db.close()

    try:
        liveness_result = check_liveness(image_data)
    except Exception as exc:
        liveness_result = {
            "liveness_passed": False,
            "score": None,
            "label": "error",
            "message": f"Liveness check failed: {exc}",
        }
    liveness_score = liveness_result.get("score")
    if not liveness_result.get("liveness_passed", False):
        processing_time_ms = round((perf_counter() - started_at) * 1000, 2)
        message = liveness_result.get("message") or "Liveness check failed."
        audit_id = None
        if audit_recognition:
            db = SessionLocal()
            try:
                attempt = _audit_recognition_safely(
                    db,
                    session_id=session_id,
                    confidence=liveness_score,
                    status="spoof",
                    image_path=capture_path,
                    message=message,
                )
                audit_id = attempt.id if attempt else None
            finally:
                db.close()

        return {
            "status": "spoof",
            "student_id": None,
            "student_code": None,
            "sample_code": None,
            "full_name": None,
            "class_name": None,
            "data_source": None,
            "is_demo": None,
            "registration_method": None,
            "student": None,
            "confidence": liveness_score if liveness_score is not None else -1.0,
            "confidence_percent": "0%" if liveness_score is None else f"{max(liveness_score, 0.0):.0%}",
            "liveness_score": liveness_score,
            "official_attendance_allowed": False,
            "official_attendance_warning": message,
            "official_attendance_warning_code": "spoof",
            "recognized": False,
            "requires_manual_confirmation": False,
            "reason": "spoof",
            "session_id": session_id,
            "processing_time_ms": processing_time_ms,
            "processing_ms": processing_time_ms,
            "audit_id": audit_id,
            "capture_path": capture_path,
            "results": [],
            "face_count": 0,
            "message": message,
        }

    try:
        if reject_multiple_faces:
            face_count = count_faces_in_image_bytes(image_data)
            if face_count > 1:
                processing_time_ms = round((perf_counter() - started_at) * 1000, 2)
                return {
                    "status": "multiple_faces",
                    "student_id": None,
                    "student_code": None,
                    "sample_code": None,
                    "full_name": None,
                    "data_source": None,
                    "is_demo": None,
                    "registration_method": None,
                    "student": None,
                    "confidence": -1.0,
                    "confidence_percent": "0%",
                    "official_attendance_allowed": False,
                    "official_attendance_warning": None,
                    "processing_time_ms": processing_time_ms,
                    "processing_ms": processing_time_ms,
                    "audit_id": None,
                    "capture_path": capture_path,
                    "message": (
                        "Ảnh có nhiều hơn một khuôn mặt. "
                        "Vui lòng dùng ảnh chỉ có một khuôn mặt."
                    ),
                }
        detected_faces = image_bytes_to_face_embeddings(image_data)
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Không đọc được ảnh. Vui lòng gửi file ảnh hợp lệ.") from exc
    except Exception as exc:
        if audit_recognition:
            db = SessionLocal()
            try:
                _audit_recognition_safely(
                    db,
                    session_id=session_id,
                    status="invalid_image",
                    image_path=capture_path,
                    message=f"Ảnh không hợp lệ: {exc}",
                )
            finally:
                db.close()
        raise HTTPException(
            status_code=400,
            detail="Không xử lý được ảnh. Vui lòng kiểm tra định dạng và chất lượng ảnh.",
        ) from exc

    if not detected_faces:
        processing_time_ms = round((perf_counter() - started_at) * 1000, 2)
        audit_id = None
        if audit_recognition:
            db = SessionLocal()
            try:
                attempt = _audit_recognition_safely(
                    db,
                    session_id=session_id,
                    confidence=-1.0,
                    status="no_face",
                    image_path=capture_path,
                    message="Không phát hiện khuôn mặt trong ảnh.",
                )
                audit_id = attempt.id if attempt else None
            finally:
                db.close()

        return {
            "status": "no_face",
            "student_id": None,
            "student_code": None,
            "sample_code": None,
            "full_name": None,
            "data_source": None,
            "is_demo": None,
            "registration_method": None,
            "student": None,
            "confidence": -1.0,
            "confidence_percent": "0%",
            "liveness_score": liveness_score,
            "official_attendance_allowed": False,
            "official_attendance_warning": None,
            "processing_time_ms": processing_time_ms,
            "processing_ms": processing_time_ms,
            "audit_id": audit_id,
            "capture_path": capture_path,
            "results": [],
            "face_count": 0,
            "message": "Không phát hiện khuôn mặt trong ảnh. Vui lòng chọn ảnh rõ mặt hơn.",
        }

    db = SessionLocal()
    try:
        db_embeddings = fetch_db_embeddings(db)
        has_registered_embeddings = bool(db_embeddings) or (
            ENABLE_LEGACY_EMBEDDINGS and bool(legacy_embeddings)
        )
        if not has_registered_embeddings:
            raise HTTPException(status_code=404, detail="Chưa có dữ liệu khuôn mặt đã đăng ký.")

        results = []
        for face in detected_faces:
            recognition_status, recognized_code, similarity = match_embedding(
                face["embedding"],
                db_embeddings,
                legacy_embeddings=legacy_embeddings,
                include_legacy=ENABLE_LEGACY_EMBEDDINGS,
            )
            student_code = recognized_code if recognized_code != "Unknown" else None
            student = None
            if student_code and recognition_status in {"success", "uncertain"}:
                student = db.query(Student).filter(Student.student_code == student_code).first()
            student_data = _serialize_student(student)
            official_warning = _official_attendance_warning(student) if official_mode else None
            official_warning_code = None
            if official_mode and not official_warning:
                official_warning, official_warning_code = _session_membership_warning(student_data, session)
            message = {
                "success": "Nhận diện khuôn mặt thành công.",
                "uncertain": "Đã phát hiện khuôn mặt nhưng chưa đủ độ tin cậy. Vui lòng xác nhận thủ công.",
                "unknown": "Đã phát hiện khuôn mặt nhưng không nhận diện được sinh viên.",
            }[recognition_status]
            if official_warning:
                message = official_warning
            audit_id = None
            if audit_recognition:
                audit_status = CROSS_CLASS_REASON_CODE if official_warning_code == CROSS_CLASS_REASON_CODE else recognition_status
                attempt = _audit_recognition_safely(
                    db,
                    session_id=session_id,
                    predicted_student_code=student_code,
                    confidence=similarity,
                    status=audit_status,
                    image_path=capture_path,
                    message=message,
                )
                audit_id = attempt.id if attempt else None

            results.append(
                {
                    "status": recognition_status,
                    "student_id": student_data["id"] if student_data else None,
                    "student_code": student_code,
                    "sample_code": student_code,
                    "full_name": student_data["full_name"] if student_data else None,
                    "class_name": student_data["class_name"] if student_data else None,
                    "data_source": student_data["data_source"] if student_data else None,
                    "is_demo": student_data["is_demo"] if student_data else None,
                    "registration_method": student_data["registration_method"] if student_data else None,
                    "student": student_data,
                    "confidence": similarity,
                    "confidence_percent": f"{max(similarity, 0.0):.0%}",
                    "liveness_score": liveness_score,
                    "bbox": face.get("bbox"),
                    "official_attendance_allowed": official_warning is None and recognition_status in {"success", "uncertain"},
                    "official_attendance_warning": official_warning,
                    "official_attendance_warning_code": official_warning_code,
                    "recognized": student_data is not None and recognition_status in {"success", "uncertain"},
                    "requires_manual_confirmation": official_warning_code == CROSS_CLASS_REASON_CODE,
                    "reason": official_warning_code,
                    "session_id": session_id,
                    "audit_id": audit_id,
                    "capture_path": capture_path,
                    "message": message,
                }
            )

        processing_time_ms = round((perf_counter() - started_at) * 1000, 2)
        for result in results:
            result["processing_time_ms"] = processing_time_ms
            result["processing_ms"] = processing_time_ms
        primary_result = results[0]
        return {
            **primary_result,
            "session_id": session_id,
            "processing_time_ms": processing_time_ms,
            "processing_ms": processing_time_ms,
            "capture_path": capture_path,
            "results": results,
            "face_count": len(results),
        }

    finally:
        db.close()


app.include_router(auth.router)
app.include_router(students.router)
app.include_router(classrooms.router)
app.include_router(subjects.router)
app.include_router(course_sections.router)
app.include_router(enrollments.router)
app.include_router(alerts.router)
app.include_router(attendance.router)
app.include_router(sessions.router)
app.include_router(reports.router)
app.include_router(faces.router)


if __name__ == "__main__":
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
