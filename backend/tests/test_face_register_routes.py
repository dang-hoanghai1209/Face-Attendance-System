import io
import os
import unittest


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import torch
from fastapi import HTTPException
from starlette.datastructures import UploadFile

from database import Base, SessionLocal, engine
from models.face_embedding import FaceEmbedding
from models.student import Student
from routes import faces


class FaceRegisterRouteTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.original_check_liveness = faces.check_liveness
        self.original_count_faces = faces.count_faces_in_image_bytes
        self.original_image_bytes_to_embedding = faces.image_bytes_to_embedding

    def tearDown(self):
        faces.check_liveness = self.original_check_liveness
        faces.count_faces_in_image_bytes = self.original_count_faces
        faces.image_bytes_to_embedding = self.original_image_bytes_to_embedding
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def add_student(self):
        student = Student(
            student_code="63123456",
            full_name="Nguyen Van A",
            class_name="63LFW",
            face_status="unregistered",
            data_source="real",
            is_demo=False,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def uploads(self, count=5):
        return [
            UploadFile(filename=f"sample_{index}.jpg", file=io.BytesIO(f"image-{index}".encode()))
            for index in range(count)
        ]

    def test_register_face_liveness_disabled_keeps_existing_flow(self):
        student = self.add_student()
        faces.check_liveness = lambda _image: {
            "liveness_passed": True,
            "score": None,
            "label": "disabled",
        }
        faces.count_faces_in_image_bytes = lambda _image: 1
        faces.image_bytes_to_embedding = lambda _image: torch.ones(512)

        response = faces.register_face_samples(
            student_code=student.student_code,
            files=self.uploads(),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["accepted_samples"], 5)
        self.assertEqual(response["total_registered_embeddings"], 1)
        self.assertEqual(
            self.db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).count(),
            1,
        )

    def test_register_face_liveness_fail_rejects_request_without_saving_embedding(self):
        student = self.add_student()
        faces.check_liveness = lambda _image: {
            "liveness_passed": False,
            "score": 0.22,
            "label": "spoof",
        }
        faces.count_faces_in_image_bytes = lambda _image: self.fail("Face detection should not run when liveness fails")
        faces.image_bytes_to_embedding = lambda _image: self.fail("Embedding should not run when liveness fails")

        with self.assertRaises(HTTPException) as ctx:
            faces.register_face_samples(
                student_code=student.student_code,
                files=self.uploads(),
                _current_user=None,
                db=self.db,
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["message"], "Xác minh liveness thất bại")
        self.assertEqual(ctx.exception.detail["liveness_score"], 0.22)
        self.assertEqual(
            self.db.query(FaceEmbedding).filter(FaceEmbedding.student_id == student.id).count(),
            0,
        )


if __name__ == "__main__":
    unittest.main()
