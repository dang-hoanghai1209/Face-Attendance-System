from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from database import get_db
from face_service import (
    aggregate_embeddings,
    count_faces_in_image_bytes,
    embedding_count,
    image_bytes_to_embedding,
    replace_student_embeddings,
)
from models.student import Student
from services.auth_service import get_current_user, require_admin


router = APIRouter(prefix="/faces", tags=["Faces"])


def _upload_name(upload: UploadFile):
    return upload.filename or "unnamed_upload"


@router.post("/register")
def register_face_samples(
    student_code: Annotated[str, Form(...)],
    files: Annotated[list[UploadFile], File(...)],
    _current_user=Depends(require_admin),
    db: Session = Depends(get_db),
):
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    if student.data_source != "real" or student.is_demo:
        raise HTTPException(
            status_code=400,
            detail="Only real students can register faces by camera.",
        )

    if len(files) < 5:
        raise HTTPException(status_code=400, detail="At least 5 face samples are required.")

    embeddings = []
    rejected_files = []

    for upload in files:
        upload_name = _upload_name(upload)
        try:
            image_bytes = upload.file.read()
            face_count = count_faces_in_image_bytes(image_bytes)
            if face_count == 0:
                rejected_files.append({"filename": upload_name, "reason": "no_face_detected"})
                continue
            if face_count > 1:
                rejected_files.append({"filename": upload_name, "reason": f"multiple_faces_detected: {face_count}"})
                continue
            embedding = image_bytes_to_embedding(image_bytes)
        except Exception as exc:
            rejected_files.append({"filename": upload_name, "reason": f"invalid_image: {exc}"})
            continue

        if embedding is None:
            rejected_files.append({"filename": upload_name, "reason": "no_face_detected"})
            continue

        embeddings.append(embedding)

    if len(embeddings) < 5:
        raise HTTPException(
            status_code=400,
            detail={
                "message": (
                    "Not enough valid face samples were detected. "
                    "Make sure the face is centered, bright, and clearly visible."
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

    return {
        "status": "success",
        "student_code": student.student_code,
        "accepted_samples": len(embeddings),
        "rejected_samples": len(rejected_files),
        "rejected_files": rejected_files,
        "total_registered_embeddings": embedding_count(db, student.id),
        "message": "Face samples registered successfully.",
    }


@router.get("/student/{student_code}")
def get_student_face_status(student_code: str, _current_user=Depends(get_current_user), db: Session = Depends(get_db)):
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

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
