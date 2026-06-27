import os
import unittest
from datetime import date


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi import HTTPException

from database import Base, SessionLocal, engine
from models.audit_log import AuditLog
from models.security_alert import SecurityAlert
from models.session import Session as ClassSession
from models.student import Student
from models.user import User
from routes.alerts import (
    AlertDismissRequest,
    count_session_alerts,
    dismiss_alert,
    get_active_session_alerts,
    get_session_alerts,
)


class AlertRouteTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
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

    def add_user(self):
        user = User(username="teacher01", password_hash="test-hash", role="teacher", is_active=True)
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def add_alert(self, session_id, alert_type="SPOOF", student_id=None, dismissed=False):
        alert = SecurityAlert(
            session_id=session_id,
            alert_type=alert_type,
            student_id=student_id,
            captured_img=f"media/alerts/{session_id}/capture.jpg",
            confidence=0.81,
            liveness_score=0.22,
            gps_lat=12.238912,
            gps_lng=109.196748,
            dismissed=dismissed,
            note="initial note",
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def test_list_alerts_includes_student_fields(self):
        session = self.add_session()
        student = self.add_student()
        alert = self.add_alert(session.id, alert_type="NOT_ENROLLED", student_id=student.id)

        response = get_session_alerts(session.id, _current_user=None, db=self.db)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]["id"], alert.id)
        self.assertEqual(response[0]["alert_type"], "NOT_ENROLLED")
        self.assertEqual(response[0]["student_code"], student.student_code)
        self.assertEqual(response[0]["full_name"], student.full_name)
        self.assertEqual(response[0]["class_name"], student.class_name)
        self.assertEqual(response[0]["confidence"], 0.81)
        self.assertEqual(response[0]["liveness_score"], 0.22)
        self.assertEqual(response[0]["gps_lat"], 12.238912)
        self.assertEqual(response[0]["gps_lng"], 109.196748)
        self.assertTrue(response[0]["has_captured_img"])
        self.assertNotIn("captured_img", response[0])
        self.assertFalse(response[0]["dismissed"])

    def test_list_active_alerts_returns_only_not_dismissed(self):
        session = self.add_session()
        active = self.add_alert(session.id, alert_type="SPOOF", dismissed=False)
        self.add_alert(session.id, alert_type="UNKNOWN_FACE", dismissed=True)

        response = get_active_session_alerts(session.id, _current_user=None, db=self.db)

        self.assertEqual([item["id"] for item in response], [active.id])
        self.assertFalse(response[0]["dismissed"])

    def test_dismiss_alert_updates_fields(self):
        session = self.add_session()
        alert = self.add_alert(session.id, alert_type="UNKNOWN_FACE")

        response = dismiss_alert(
            alert.id,
            AlertDismissRequest(note="Đã kiểm tra", dismissed_by="lecturer"),
            current_user=None,
            db=self.db,
        )

        self.assertTrue(response["dismissed"])
        self.assertEqual(response["dismissed_by"], "lecturer")
        self.assertEqual(response["note"], "Đã kiểm tra")
        self.assertIsNotNone(response["dismissed_at"])
        self.assertTrue(response["has_captured_img"])
        self.assertNotIn("captured_img", response)

        with self.assertRaises(HTTPException) as ctx:
            dismiss_alert(999, AlertDismissRequest(), current_user=None, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_dismiss_alert_writes_audit_log(self):
        session = self.add_session()
        student = self.add_student()
        user = self.add_user()
        alert = self.add_alert(session.id, alert_type="NOT_ENROLLED", student_id=student.id)

        dismiss_alert(
            alert.id,
            AlertDismissRequest(note="Reviewed and accepted"),
            current_user=user,
            db=self.db,
        )

        log = self.db.query(AuditLog).filter(AuditLog.action == "security_alert_dismissed").one()
        self.assertEqual(log.actor_user_id, user.id)
        self.assertEqual(log.actor_role, "teacher")
        self.assertEqual(log.target_type, "security_alert")
        self.assertEqual(log.target_id, str(alert.id))
        self.assertEqual(log.details["session_id"], session.id)
        self.assertEqual(log.details["student_id"], student.id)
        self.assertEqual(log.details["student_code"], student.student_code)
        self.assertEqual(log.details["reason"], "Reviewed and accepted")
        self.assertFalse(log.details["old_value"]["dismissed"])
        self.assertTrue(log.details["new_value"]["dismissed"])
        self.assertEqual(log.details["old_value"]["note"], "initial note")
        self.assertEqual(log.details["new_value"]["note"], "Reviewed and accepted")

    def test_count_alerts_by_type_counts_only_active(self):
        session = self.add_session()
        self.add_alert(session.id, alert_type="SPOOF")
        self.add_alert(session.id, alert_type="UNKNOWN_FACE")
        self.add_alert(session.id, alert_type="NOT_ENROLLED")
        self.add_alert(session.id, alert_type="LATE_ENTRY", dismissed=True)

        response = count_session_alerts(session.id, _current_user=None, db=self.db)

        self.assertEqual(response["session_id"], session.id)
        self.assertEqual(response["total_active"], 3)
        self.assertEqual(response["by_type"]["SPOOF"], 1)
        self.assertEqual(response["by_type"]["UNKNOWN_FACE"], 1)
        self.assertEqual(response["by_type"]["NOT_ENROLLED"], 1)
        self.assertEqual(response["by_type"]["LATE_ENTRY"], 0)

    def test_filter_dismissed_query(self):
        session = self.add_session()
        active = self.add_alert(session.id, alert_type="SPOOF", dismissed=False)
        dismissed = self.add_alert(session.id, alert_type="UNKNOWN_FACE", dismissed=True)

        active_response = get_session_alerts(session.id, dismissed=False, _current_user=None, db=self.db)
        dismissed_response = get_session_alerts(session.id, dismissed=True, _current_user=None, db=self.db)

        self.assertEqual([item["id"] for item in active_response], [active.id])
        self.assertEqual([item["id"] for item in dismissed_response], [dismissed.id])


if __name__ == "__main__":
    unittest.main()
