import os
import unittest
from datetime import date


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from database import Base, SessionLocal, engine
from models.enrollment import Enrollment
from models.security_alert import SecurityAlert
from models.session import Session as ClassSession
from models.student import Student
from schema_sync import sync_schema


class AddonEnrollmentAlertModelTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

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

    def test_metadata_creates_enrollment_and_security_alert_tables(self):
        inspector = inspect(engine)
        tables = set(inspector.get_table_names())

        self.assertIn("enrollments", tables)
        self.assertIn("security_alerts", tables)

        enrollment_columns = {column["name"] for column in inspector.get_columns("enrollments")}
        alert_columns = {column["name"] for column in inspector.get_columns("security_alerts")}

        self.assertTrue({"id", "session_id", "student_id", "enrolled_at", "note"}.issubset(enrollment_columns))
        self.assertTrue(
            {
                "id",
                "session_id",
                "alert_type",
                "student_id",
                "captured_img",
                "confidence",
                "liveness_score",
                "gps_lat",
                "gps_lng",
                "dismissed",
                "dismissed_by",
                "dismissed_at",
                "note",
                "created_at",
            }.issubset(alert_columns)
        )

    def test_enrollment_session_student_unique_constraint(self):
        student = self.add_student()
        session = self.add_session()
        self.db.add(Enrollment(session_id=session.id, student_id=student.id))
        self.db.commit()

        self.db.add(Enrollment(session_id=session.id, student_id=student.id))
        with self.assertRaises(IntegrityError):
            self.db.commit()
        self.db.rollback()

    def test_schema_sync_handles_legacy_addon_tables_with_data(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)
        with engine.begin() as connection:
            connection.execute(text("CREATE TABLE enrollments (id INTEGER PRIMARY KEY, student_id INTEGER NOT NULL)"))
            connection.execute(text("INSERT INTO enrollments (id, student_id) VALUES (1, 1)"))
            connection.execute(text("CREATE TABLE security_alerts (id INTEGER PRIMARY KEY, session_id INTEGER)"))
            connection.execute(text("INSERT INTO security_alerts (id, session_id) VALUES (1, 1)"))

        sync_schema(engine)

        inspector = inspect(engine)
        enrollment_columns = {column["name"] for column in inspector.get_columns("enrollments")}
        alert_columns = {column["name"] for column in inspector.get_columns("security_alerts")}

        self.assertTrue({"session_id", "enrolled_at", "note"}.issubset(enrollment_columns))
        self.assertTrue({"dismissed", "created_at", "alert_type"}.issubset(alert_columns))
        self.db = SessionLocal()
        enrollment = self.db.query(Enrollment).first()
        alert = self.db.query(SecurityAlert).first()
        self.assertEqual(enrollment.student_id, 1)
        self.assertFalse(alert.dismissed)


if __name__ == "__main__":
    unittest.main()
