from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from face_service import (
    aggregate_embeddings,
    check_liveness,
    count_faces_in_image_bytes,
    embedding_count,
    image_bytes_to_embedding,
    replace_student_embeddings,
)
from models.student import Student
from services.audit_service import audit_safely
from services.auth_service import get_current_user, require_role


router = APIRouter(prefix="/faces", tags=["Faces"])
require_face_registrar = require_role("admin", "teacher")


def _upload_name(upload: UploadFile):
    return upload.filename or "tep_tai_len_khong_ten"


@router.post("/register")
def register_face_samples(
    student_code: Annotated[str, Form(...)],
    files: Annotated[list[UploadFile], File(...)],
    _current_user=Depends(require_face_registrar),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")

    if student.data_source != "real" or student.is_demo:
        raise HTTPException(
            status_code=400,
            detail="Chỉ sinh viên thật mới được đăng ký khuôn mặt bằng camera.",
        )

    if len(files) < 5:
        raise HTTPException(status_code=400, detail="Cần ít nhất 5 ảnh mẫu khuôn mặt.")

    embeddings = []
    rejected_files = []

    for upload in files:
        upload_name = _upload_name(upload)
        try:
            image_bytes = upload.file.read()
            liveness_result = check_liveness(image_bytes)
            if not liveness_result.get("liveness_passed", False):
                raise HTTPException(
                    status_code=403,
                    detail={
                        "message": "Xác minh liveness thất bại",
                        "filename": upload_name,
                        "liveness_score": liveness_result.get("score"),
                        "liveness_label": liveness_result.get("label"),
                    },
                )
            face_count = count_faces_in_image_bytes(image_bytes)
            if face_count == 0:
                rejected_files.append({"filename": upload_name, "reason": "Không phát hiện khuôn mặt."})
                continue
            if face_count > 1:
                rejected_files.append({"filename": upload_name, "reason": f"Phát hiện nhiều khuôn mặt: {face_count}."})
                continue
            embedding = image_bytes_to_embedding(image_bytes)
        except HTTPException:
            raise
        except Exception:
            rejected_files.append({"filename": upload_name, "reason": "Ảnh không hợp lệ hoặc không thể xử lý."})
            continue

        if embedding is None:
            rejected_files.append({"filename": upload_name, "reason": "Không phát hiện khuôn mặt."})
            continue

        embeddings.append(embedding)

    if len(embeddings) < 5:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "Không phát hiện đủ ảnh mẫu khuôn mặt hợp lệ. "
                    "Vui lòng đảm bảo khuôn mặt ở giữa khung hình, đủ sáng và nhìn rõ."
                ),
                "accepted_samples": len(embeddings),
                "rejected_samples": len(rejected_files),
                "rejected_files": rejected_files,
            },
        )

    mean_embedding = aggregate_embeddings(embeddings)
    replace_student_embeddings(db, student.id, [mean_embedding], source="webcam_mean")
    student.face_status = "registered"
    student.registration_method = "camera"
    db.commit()
    audit_safely(
        db,
        action="face_registered",
        actor_user=_current_user,
        target_type="student",
        target_id=student.id,
        details={"student_code": student.student_code, "accepted_samples": len(embeddings)},
    )

    return {
        "status": "success",
        "student_code": student.student_code,
        "accepted_samples": len(embeddings),
        "rejected_samples": len(rejected_files),
        "rejected_files": rejected_files,
        "total_registered_embeddings": embedding_count(db, student.id),
        "message": "Đăng ký khuôn mặt thành công.",
    }


@router.get("/student/{student_code}")
def get_student_face_status(student_code: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Sinh viên không hợp lệ.")

    registered_embeddings = embedding_count(db, student.id)

    return {
        "student_code": student.student_code,
        "full_name": student.full_name,
        "registered_embeddings": registered_embeddings,
        "face_status": student.face_status if student.face_status else ("registered" if registered_embeddings > 0 else "unregistered"),
        "data_source": student.data_source,
        "registration_method": student.registration_method,
        "is_demo": student.is_demo,
    }
