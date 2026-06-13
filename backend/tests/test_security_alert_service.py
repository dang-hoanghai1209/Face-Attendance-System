import os
import unittest
from datetime import date
from pathlib import Path


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database import Base, SessionLocal, engine
from models.security_alert import SecurityAlert
from models.session import Session as ClassSession
from models.student import Student
from services import security_alert_service


class SecurityAlertServiceTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()
        self.created_files = []

    def tearDown(self):
        self.db.close()
        for path in self.created_files:
            if path.exists():
                path.unlink()
        Base.metadata.drop_all(bind=engine)

    def add_session(self):
        session = ClassSession(
            subject="Database",
            class_name="63LFW",
            session_date=date(2026, 6, 1),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def add_student(self):
        student = Student(
            student_code="63123456",
            full_name="Nguyen Van A",
            class_name="63LFW",
            data_source="real",
            is_demo=False,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def test_create_alert_creates_record_with_default_dismissed_false(self):
        session = self.add_session()

        alert = security_alert_service.create_alert(
            self.db,
            session_id=session.id,
            alert_type="LATE_ENTRY",
            confidence=0.91,
            note="after deadline",
        )

        persisted = self.db.query(SecurityAlert).filter(SecurityAlert.id == alert.id).one()
        self.assertEqual(persisted.alert_type, "LATE_ENTRY")
        self.assertEqual(persisted.session_id, session.id)
        self.assertEqual(persisted.confidence, 0.91)
        self.assertEqual(persisted.note, "after deadline")
        self.assertFalse(persisted.dismissed)
        self.assertIsNone(persisted.captured_img)

    def test_create_alert_with_image_bytes_saves_capture_under_session_directory(self):
        session = self.add_session()
        image_bytes = b"fake-jpeg-bytes"

        alert = security_alert_service.create_alert(
            self.db,
            session_id=session.id,
            alert_type="UNKNOWN_FACE",
            image_bytes=image_bytes,
            confidence=0.42,
            gps_lat=12.238912,
            gps_lng=109.196748,
        )

        self.assertIsNotNone(alert.captured_img)
        self.assertTrue(alert.captured_img.startswith(f"media/alerts/{session.id}/"))
        self.assertTrue(alert.captured_img.endswith(".jpg"))
        saved_path = security_alert_service.BASE_DIR / Path(alert.captured_img)
        self.created_files.append(saved_path)
        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.read_bytes(), image_bytes)

    def test_create_alert_persists_student_liveness_and_gps_fields(self):
        session = self.add_session()
        student = self.add_student()

        alert = security_alert_service.create_alert(
            self.db,
            session_id=session.id,
            alert_type="SPOOF",
            student_id=student.id,
            confidence=0.33,
            liveness_score=0.12,
            gps_lat=12.2,
            gps_lng=109.1,
        )

        self.assertEqual(alert.student_id, student.id)
        self.assertEqual(alert.alert_type, "SPOOF")
        self.assertEqual(alert.confidence, 0.33)
        self.assertEqual(alert.liveness_score, 0.12)
        self.assertEqual(alert.gps_lat, 12.2)
        self.assertEqual(alert.gps_lng, 109.1)


if __name__ == "__main__":
    unittest.main()
