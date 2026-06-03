import io
import os
import unittest
from datetime import date, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import torch
from fastapi import HTTPException
from starlette.datastructures import UploadFile

import main
from database import Base, SessionLocal, engine
from models.session import Session as ClassSession
from models.student import Student


class RecognitionEndpointTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.original_image_bytes_to_embedding = main.image_bytes_to_embedding
        self.original_count_faces = main.count_faces_in_image_bytes
        self.original_fetch_db_embeddings = main.fetch_db_embeddings
        self.original_match_embedding = main.match_embedding

    def tearDown(self):
        main.image_bytes_to_embedding = self.original_image_bytes_to_embedding
        main.count_faces_in_image_bytes = self.original_count_faces
        main.fetch_db_embeddings = self.original_fetch_db_embeddings
        main.match_embedding = self.original_match_embedding
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def add_session(self):
        session = ClassSession(
            subject="Database",
            class_name="63LFW",
            session_date=date(2026, 6, 1),
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def add_student(self, student_code="63123456", class_name="63LFW", face_status="registered"):
        student = Student(
            student_code=student_code,
            full_name="Cross Class Student",
            class_name=class_name,
            face_status=face_status,
            data_source="real",
            is_demo=False,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def upload(self, content=b"fake-image"):
        return UploadFile(filename="capture.jpg", file=io.BytesIO(content))

    def test_recognize_requires_existing_session(self):
        with self.assertRaises(HTTPException) as ctx:
            main._recognize_uploaded_face(file=self.upload(), session_id=999)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertIn("Không tìm thấy buổi học", ctx.exception.detail)

    def test_recognize_empty_file_returns_clear_400(self):
        session = self.add_session()

        with self.assertRaises(HTTPException) as ctx:
            main._recognize_uploaded_face(file=self.upload(b""), session_id=session.id)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertIn("file tải lên rỗng", ctx.exception.detail)

    def test_recognize_without_registered_embeddings_returns_clear_404(self):
        session = self.add_session()
        main.count_faces_in_image_bytes = lambda _image: 1
        main.image_bytes_to_embedding = lambda _image: torch.zeros(512)
        main.fetch_db_embeddings = lambda _db: []

        with self.assertRaises(HTTPException) as ctx:
            main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Chưa có dữ liệu khuôn mặt đã đăng ký.")

    def test_recognize_cross_class_returns_manual_confirmation_reason(self):
        session = ClassSession(
            subject="Database",
            class_name="64CNTT",
            session_date=date(2026, 6, 1),
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        self.add_student(student_code="63123456", class_name="63LFW")
        main.count_faces_in_image_bytes = lambda _image: 1
        main.image_bytes_to_embedding = lambda _image: torch.zeros(512)
        main.fetch_db_embeddings = lambda _db: [object()]
        main.match_embedding = lambda *_args, **_kwargs: ("success", "63123456", 0.91)

        result = main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertFalse(result["official_attendance_allowed"])
        self.assertEqual(result["reason"], "cross_class_requires_manual_confirmation")
        self.assertIn("Sinh viên thuộc lớp 63LFW, khác lớp chính của buổi học 64CNTT", result["message"])


if __name__ == "__main__":
    unittest.main()
