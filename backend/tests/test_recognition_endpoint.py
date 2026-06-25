import io
import importlib
import json
import os
import unittest
from datetime import date, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

import torch
from fastapi import HTTPException
from starlette.datastructures import UploadFile

import face_service
import main
from database import Base, SessionLocal, engine
from models.attendance import Attendance
from models.recognition_attempt import RecognitionAttempt
from models.security_alert import SecurityAlert
from models.session import Session as ClassSession
from models.student import Student
from services import attendance_service, report_service, security_alert_service


class RecognitionEndpointTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.original_check_liveness = main.check_liveness
        self.original_image_bytes_to_embedding = main.image_bytes_to_embedding
        self.original_image_bytes_to_face_embeddings = main.image_bytes_to_face_embeddings
        self.original_evaluate_uploaded_face_quality = main.evaluate_uploaded_face_quality
        self.original_count_faces = main.count_faces_in_image_bytes
        self.original_fetch_db_embeddings = main.fetch_db_embeddings
        self.original_match_embedding = main.match_embedding
        self.original_liveness_enabled = face_service.ENABLE_LIVENESS
        self.original_liveness_threshold = face_service.LIVENESS_THRESHOLD
        self.original_liveness_model = face_service.LIVENESS_MODEL
        main.check_liveness = lambda _image: {
            "liveness_passed": True,
            "score": 0.99,
            "label": "live",
            "threshold": 0.45,
        }

    def tearDown(self):
        main.check_liveness = self.original_check_liveness
        main.image_bytes_to_embedding = self.original_image_bytes_to_embedding
        main.image_bytes_to_face_embeddings = self.original_image_bytes_to_face_embeddings
        main.evaluate_uploaded_face_quality = self.original_evaluate_uploaded_face_quality
        main.count_faces_in_image_bytes = self.original_count_faces
        main.fetch_db_embeddings = self.original_fetch_db_embeddings
        main.match_embedding = self.original_match_embedding
        face_service.ENABLE_LIVENESS = self.original_liveness_enabled
        face_service.LIVENESS_THRESHOLD = self.original_liveness_threshold
        face_service.LIVENESS_MODEL = self.original_liveness_model
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
        main.image_bytes_to_face_embeddings = lambda _image: [
            {"embedding": torch.zeros(512), "bbox": {"x": 1, "y": 2, "w": 3, "h": 4}}
        ]
        main.fetch_db_embeddings = lambda _db: []

        with self.assertRaises(HTTPException) as ctx:
            main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail, "Chưa có dữ liệu khuôn mặt đã đăng ký.")

    def test_recognize_cross_class_returns_not_enrolled_without_manual_confirmation(self):
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
        main.image_bytes_to_face_embeddings = lambda _image: [
            {"embedding": torch.zeros(512), "bbox": {"x": 1, "y": 2, "w": 3, "h": 4}}
        ]
        main.fetch_db_embeddings = lambda _db: [object()]
        main.match_embedding = lambda *_args, **_kwargs: ("success", "63123456", 0.91)

        result = main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertFalse(result["official_attendance_allowed"])
        self.assertTrue(result["recognized"])
        self.assertNotIn("requires_manual_confirmation", result)
        self.assertEqual(result["reason"], "not_enrolled")
        self.assertEqual(result["session_id"], session.id)
        self.assertIsNotNone(result["audit_id"])
        audit = self.db.query(RecognitionAttempt).filter(RecognitionAttempt.id == result["audit_id"]).first()
        self.assertEqual(audit.status, "not_enrolled")
        self.assertEqual(result["message"], "Sinh viên không thuộc danh sách lớp học phần này")

    def test_cross_class_recognize_audit_does_not_create_attendance(self):
        session = ClassSession(
            subject="Software Testing",
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
        main.image_bytes_to_face_embeddings = lambda _image: [
            {"embedding": torch.zeros(512), "bbox": {"x": 1, "y": 2, "w": 3, "h": 4}}
        ]
        main.fetch_db_embeddings = lambda _db: [object()]
        main.match_embedding = lambda *_args, **_kwargs: ("success", "63123456", 0.91)

        recognition = main._recognize_uploaded_face(file=self.upload(), session_id=session.id)
        _session, rows = report_service.build_session_report(session.id, self.db)
        by_code = {row["student_code"]: row for row in rows}

        self.assertEqual(recognition["reason"], "not_enrolled")
        self.assertIsNotNone(recognition["audit_id"])
        self.assertNotIn("63123456", by_code)
        self.assertEqual(self.db.query(Attendance).count(), 0)

    def test_recognize_no_face_returns_empty_results(self):
        session = self.add_session()
        main.image_bytes_to_face_embeddings = lambda _image: []

        result = main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertEqual(result["status"], "no_face")
        self.assertEqual(result["results"], [])
        self.assertEqual(result["face_count"], 0)

    def test_recognize_liveness_fail_returns_spoof_without_recognition(self):
        session = self.add_session()
        main.check_liveness = lambda _image: {
            "liveness_passed": False,
            "score": 0.31,
            "label": "spoof",
            "message": "Liveness check failed.",
        }
        main.image_bytes_to_face_embeddings = lambda _image: self.fail("Recognition should not run when liveness fails")

        result = main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertEqual(result["status"], "spoof")
        self.assertEqual(result["liveness_score"], 0.31)
        self.assertEqual(result["confidence"], 0.31)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["face_count"], 0)
        self.assertIsNone(result["student_code"])
        self.assertIsNone(result["full_name"])
        self.assertIsNone(result["student"])
        self.assertIsNotNone(result["audit_id"])
        audit = self.db.query(RecognitionAttempt).filter(RecognitionAttempt.id == result["audit_id"]).first()
        self.assertEqual(audit.status, "spoof")

    def test_recognize_quality_fail_returns_face_unclear_without_embedding_and_alerts(self):
        session = self.add_session()
        main.evaluate_uploaded_face_quality = lambda _image: {
            "face_detected": True,
            "face_count": 1,
            "bbox": {"x": 10, "y": 20, "w": 80, "h": 90},
            "detection_probability": 0.98,
            "reason_code": "LOW_SHARPNESS",
            "final_result": "FACE_UNCLEAR",
            "passed": False,
            "metrics": {
                "sharpness": 2.0,
                "brightness": 120.0,
                "face_size_ratio": 0.2,
                "yaw_estimate": 0.0,
                "landmark_geometry_valid": True,
            },
        }
        main.image_bytes_to_face_embeddings = lambda _image: self.fail("Embedding should not run when quality fails")

        result = main._recognize_uploaded_face(file=self.upload(b"unclear-image"), session_id=session.id)

        self.assertEqual(result["status"], "FACE_UNCLEAR")
        self.assertEqual(result["reason_code"], "LOW_SHARPNESS")
        self.assertTrue(result["retry_allowed"])
        self.assertFalse(result["official_attendance_allowed"])
        self.assertFalse(result["recognized"])
        self.assertIsNone(result["confidence"])
        self.assertIsNone(result["confidence_percent"])
        self.assertEqual(result["detection_confidence"], 0.98)
        self.assertEqual(result["detection_confidence_percent"], "98%")
        self.assertEqual(result["student_code"], None)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["face_count"], 1)
        self.assertEqual(result["message"], main.FACE_UNCLEAR_MESSAGE)
        self.assertEqual(self.db.query(Attendance).count(), 0)

        alert = self.db.query(SecurityAlert).filter(SecurityAlert.id == result["alert_id"]).one()
        self.assertEqual(alert.alert_type, "FACE_UNCLEAR")
        self.assertEqual(alert.session_id, session.id)
        self.assertEqual(alert.confidence, 0.98)
        alert_note = json.loads(alert.note)
        self.assertEqual(alert_note["reason_code"], "LOW_SHARPNESS")
        self.assertEqual(alert_note["detection_confidence"], 0.98)
        self.assertEqual(alert_note["quality"]["sharpness"], 2.0)
        self.assertEqual(alert_note["quality"]["landmark_geometry_valid"], True)
        self.assertTrue(alert.captured_img.startswith(f"media/security_snapshots/{session.id}/"))
        self.assertTrue(alert.captured_img.endswith("_LOW_SHARPNESS.jpg"))
        saved_path = security_alert_service.BASE_DIR / alert.captured_img
        self.assertTrue(saved_path.exists())
        saved_path.unlink()

        audit = self.db.query(RecognitionAttempt).filter(RecognitionAttempt.id == result["audit_id"]).first()
        self.assertEqual(audit.status, "FACE_UNCLEAR")

    def test_recognize_liveness_error_returns_spoof_without_recognition(self):
        session = self.add_session()
        face_service.ENABLE_LIVENESS = True
        face_service.LIVENESS_THRESHOLD = 0.8
        face_service.LIVENESS_MODEL = "minifasnet"
        main.check_liveness = face_service.check_liveness
        main.image_bytes_to_face_embeddings = lambda _image: self.fail("Recognition should not run when liveness is unavailable")

        result = main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertEqual(result["status"], "spoof")
        self.assertIn("Không đạt kiểm tra khuôn mặt thật", result["message"])
        self.assertIsNone(result["liveness_score"])
        self.assertFalse(result["liveness_passed"])
        self.assertEqual(result["liveness_label"], "error")
        self.assertEqual(result["liveness_threshold"], main.LIVENESS_THRESHOLD)
        self.assertEqual(result["confidence"], -1.0)
        self.assertEqual(result["results"], [])
        self.assertEqual(result["face_count"], 0)
        self.assertIsNotNone(result["audit_id"])
        audit = self.db.query(RecognitionAttempt).filter(RecognitionAttempt.id == result["audit_id"]).first()
        self.assertEqual(audit.status, "spoof")

    def test_recognize_returns_multi_face_results_with_backward_compatible_top_level(self):
        session = self.add_session()
        first_student = self.add_student(student_code="63123456", class_name="63LFW")
        second_student = self.add_student(student_code="63123457", class_name="63LFW")
        main.image_bytes_to_face_embeddings = lambda _image: [
            {"embedding": torch.ones(512), "bbox": {"x": 10, "y": 20, "w": 30, "h": 40}},
            {"embedding": torch.zeros(512), "bbox": {"x": 50, "y": 60, "w": 35, "h": 45}},
        ]
        main.fetch_db_embeddings = lambda _db: [object()]

        def fake_match(embedding, *_args, **_kwargs):
            if torch.equal(embedding, torch.ones(512)):
                return "success", first_student.student_code, 0.93
            return "uncertain", second_student.student_code, 0.67

        main.match_embedding = fake_match

        result = main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertEqual(result["status"], "success")
        self.assertEqual(result["student_code"], "63123456")
        self.assertEqual(result["confidence"], 0.93)
        self.assertEqual(result["full_name"], "Cross Class Student")
        self.assertIsNotNone(result["student"])
        self.assertIsNotNone(result["audit_id"])
        self.assertEqual(result["face_count"], 2)
        self.assertEqual(len(result["results"]), 2)
        required_fields = {
            "student_code",
            "full_name",
            "class_name",
            "confidence",
            "status",
            "liveness_score",
            "liveness_passed",
            "liveness_label",
            "liveness_threshold",
            "bbox",
        }
        for item in result["results"]:
            self.assertTrue(required_fields.issubset(item.keys()))
        self.assertEqual(result["results"][0]["student_code"], "63123456")
        self.assertEqual(result["results"][0]["full_name"], "Cross Class Student")
        self.assertEqual(result["results"][0]["class_name"], "63LFW")
        self.assertEqual(result["results"][0]["confidence"], 0.93)
        self.assertEqual(result["results"][0]["status"], "success")
        self.assertEqual(result["results"][0]["liveness_score"], 0.99)
        self.assertTrue(result["results"][0]["liveness_passed"])
        self.assertEqual(result["results"][0]["liveness_label"], "live")
        self.assertEqual(result["results"][0]["liveness_threshold"], 0.45)
        self.assertEqual(result["results"][0]["bbox"], {"x": 10, "y": 20, "w": 30, "h": 40})
        self.assertEqual(result["results"][1]["status"], "uncertain")
        self.assertEqual(result["results"][1]["student_code"], "63123457")
        self.assertEqual(self.db.query(RecognitionAttempt).count(), 2)

    def test_recognize_multi_face_threshold_boundaries(self):
        session = self.add_session()
        self.add_student(student_code="63123456", class_name="63LFW")
        self.add_student(student_code="63123457", class_name="63LFW")
        main.image_bytes_to_face_embeddings = lambda _image: [
            {"embedding": torch.full((512,), 1.0), "bbox": {"x": 1, "y": 1, "w": 10, "h": 10}},
            {"embedding": torch.full((512,), 2.0), "bbox": {"x": 2, "y": 2, "w": 10, "h": 10}},
            {"embedding": torch.full((512,), 3.0), "bbox": {"x": 3, "y": 3, "w": 10, "h": 10}},
        ]
        main.fetch_db_embeddings = lambda _db: [object()]

        def fake_match(embedding, *_args, **_kwargs):
            marker = embedding[0].item()
            if marker == 1.0:
                return "success", "63123456", main.THRESHOLD_CONFIRM
            if marker == 2.0:
                return "uncertain", "63123457", main.THRESHOLD_UNCERTAIN
            return "unknown", "Unknown", main.THRESHOLD_UNCERTAIN - 0.01

        main.match_embedding = fake_match

        result = main._recognize_uploaded_face(file=self.upload(), session_id=session.id)

        self.assertEqual([item["status"] for item in result["results"]], ["success", "uncertain", "unknown"])
        self.assertEqual(result["results"][0]["confidence"], main.THRESHOLD_CONFIRM)
        self.assertEqual(result["results"][1]["confidence"], main.THRESHOLD_UNCERTAIN)
        self.assertLess(result["results"][2]["confidence"], main.THRESHOLD_UNCERTAIN)
        self.assertIsNone(result["results"][2]["student_code"])
        self.assertIsNone(result["results"][2]["full_name"])
        self.assertIsNone(result["results"][2]["class_name"])
        self.assertEqual(result["results"][2]["liveness_score"], 0.99)
        self.assertTrue(result["results"][2]["liveness_passed"])
        self.assertEqual(result["results"][2]["liveness_label"], "live")
        self.assertEqual(result["results"][2]["liveness_threshold"], 0.45)
        self.assertEqual(result["results"][2]["bbox"], {"x": 3, "y": 3, "w": 10, "h": 10})

    def test_invalid_liveness_threshold_env_falls_back_without_import_crash(self):
        original_env = os.environ.get("LIVENESS_THRESHOLD")
        original_enabled_env = os.environ.get("ENABLE_LIVENESS")
        os.environ["LIVENESS_THRESHOLD"] = "not-a-float"
        os.environ["ENABLE_LIVENESS"] = "false"
        try:
            reloaded = importlib.reload(face_service)
            self.assertEqual(reloaded.LIVENESS_THRESHOLD, 0.45)
            self.assertEqual(reloaded.check_liveness(b"image")["label"], "disabled")
        finally:
            if original_env is None:
                os.environ.pop("LIVENESS_THRESHOLD", None)
            else:
                os.environ["LIVENESS_THRESHOLD"] = original_env
            if original_enabled_env is None:
                os.environ.pop("ENABLE_LIVENESS", None)
            else:
                os.environ["ENABLE_LIVENESS"] = original_enabled_env
            importlib.reload(face_service)


if __name__ == "__main__":
    unittest.main()
