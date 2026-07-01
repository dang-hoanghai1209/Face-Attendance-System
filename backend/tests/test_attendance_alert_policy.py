import os
import unittest
from datetime import date, datetime, time
from pathlib import Path


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database import Base, SessionLocal, engine
from models.attendance import Attendance
from models.enrollment import Enrollment
from models.security_alert import SecurityAlert
from models.session import Session as ClassSession
from models.student import Student
from services import attendance_service, security_alert_service


class AttendanceAlertPolicyTests(unittest.TestCase):
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

    def add_student(self, code="SV001", full_name="Student 1", class_name="64-TTQL-1"):
        student = Student(
            student_code=code,
            full_name=full_name,
            class_name=class_name,
            face_status="registered",
            data_source="real",
            is_demo=False,
            registration_method="camera",
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def add_session(self):
        session = ClassSession(
            subject="AI",
            class_name="64-TTQL-1",
            latitude=12.238912,
            longitude=109.196748,
            radius_meters=20,
            session_date=date(2026, 6, 1),
            start_time=time(7, 30),
            end_time=time(9, 30),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def enroll(self, session, students):
        for student in students:
            self.db.add(Enrollment(session_id=session.id, student_id=student.id, status="active"))
        self.db.commit()

    def add_enrolled_session(self):
        target = self.add_student()
        extras = [
            self.add_student(code=f"SV00{index}", full_name=f"Student {index}")
            for index in range(2, 6)
        ]
        session = self.add_session()
        self.enroll(session, [target, *extras])
        return target, session

    def patch_now(self, value):
        original_now = attendance_service.now_in_app_timezone
        attendance_service.now_in_app_timezone = lambda: value
        self.addCleanup(lambda: setattr(attendance_service, "now_in_app_timezone", original_now))

    def alerts(self, alert_type=None):
        query = self.db.query(SecurityAlert)
        if alert_type:
            query = query.filter(SecurityAlert.alert_type == alert_type)
        return query.all()

    def attendance_count(self):
        return self.db.query(Attendance).count()

    def write_source_capture(self, content=b"unclear-face"):
        relative_path = Path("media") / "recognition_attempts" / "test_face_unclear.jpg"
        path = security_alert_service.BASE_DIR / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
        self.created_files.append(path)
        return str(relative_path).replace("\\", "/"), content

    def test_liveness_fail_creates_spoof_alert_without_attendance(self):
        student, session = self.add_enrolled_session()

        response = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            confidence=0.91,
            image_path="media/captures/spoof.jpg",
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            liveness_passed=False,
            liveness_score=0.12,
        )

        alerts = self.alerts("SPOOF")
        self.assertEqual(response["status"], "spoof")
        self.assertTrue(response["has_captured_img"])
        self.assertNotIn("captured_img", response)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].captured_img, "media/captures/spoof.jpg")
        self.assertEqual(alerts[0].liveness_score, 0.12)
        self.assertEqual(self.attendance_count(), 0)

    def test_unknown_face_creates_unknown_alert_without_attendance(self):
        _student, session = self.add_enrolled_session()

        response = attendance_service.record_checkin(
            self.db,
            "UNKNOWN",
            session.id,
            confidence=0.2,
            image_path="media/captures/unknown.jpg",
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            recognition_status="unknown",
        )

        alerts = self.alerts("UNKNOWN_FACE")
        self.assertEqual(response["status"], "unknown")
        self.assertTrue(response["has_captured_img"])
        self.assertNotIn("captured_img", response)
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].confidence, 0.2)
        self.assertEqual(alerts[0].captured_img, "media/captures/unknown.jpg")
        self.assertEqual(self.attendance_count(), 0)

    def test_face_unclear_creates_alert_snapshot_without_attendance(self):
        _student, session = self.add_enrolled_session()
        image_path, image_bytes = self.write_source_capture()

        response = attendance_service.record_checkin(
            self.db,
            None,
            session.id,
            confidence=0.98,
            image_path=image_path,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            recognition_status="FACE_UNCLEAR",
            reason_code="LOW_SHARPNESS",
            quality_details={
                "sharpness": 2.0,
                "brightness": 120.0,
                "face_size_ratio": 0.2,
                "detection_confidence": 0.98,
                "failed_checks": ["LOW_SHARPNESS"],
            },
        )

        alerts = self.alerts("FACE_UNCLEAR")
        self.assertEqual(response["status"], "FACE_UNCLEAR")
        self.assertFalse(response["success"])
        self.assertFalse(response["recorded"])
        self.assertFalse(response["attendance_created"])
        self.assertTrue(response["retry_allowed"])
        self.assertTrue(response["alert_created"])
        self.assertEqual(response["alert_type"], "FACE_UNCLEAR")
        self.assertEqual(response["reason_code"], "LOW_SHARPNESS")
        self.assertEqual(response["quality"]["failed_checks"], ["LOW_SHARPNESS"])
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].alert_type, "FACE_UNCLEAR")
        self.assertEqual(alerts[0].confidence, 0.98)
        self.assertIsNone(alerts[0].student_id)
        self.assertIsInstance(alerts[0].captured_img, str)
        self.assertTrue(alerts[0].captured_img.startswith(f"media/security_snapshots/{session.id}/"))
        self.assertTrue(alerts[0].captured_img.endswith("_LOW_SHARPNESS.jpg"))
        self.assertEqual(response["snapshot_path"], f"/{alerts[0].captured_img}")
        saved_path = security_alert_service.BASE_DIR / Path(alerts[0].captured_img)
        self.created_files.append(saved_path)
        self.assertTrue(saved_path.exists())
        self.assertEqual(saved_path.read_bytes(), image_bytes)
        self.assertEqual(self.attendance_count(), 0)

    def test_recognized_student_not_enrolled_creates_alert_without_attendance(self):
        target = self.add_student(code="SV999", full_name="Not Enrolled")
        enrolled = [
            self.add_student(code=f"SV10{index}", full_name=f"Enrolled {index}")
            for index in range(5)
        ]
        session = self.add_session()
        self.enroll(session, enrolled)

        response = attendance_service.record_checkin(
            self.db,
            target.student_code,
            session.id,
            confidence=0.89,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            recognition_status="success",
        )

        alerts = self.alerts("NOT_ENROLLED")
        self.assertEqual(response["status"], "not_enrolled")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].student_id, target.id)
        self.assertEqual(self.attendance_count(), 0)

    def test_zero_enrollments_creates_not_enrolled_alert_without_attendance(self):
        student = self.add_student()
        session = self.add_session()

        response = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            confidence=0.89,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            recognition_status="success",
        )

        alerts = self.alerts("NOT_ENROLLED")
        self.assertEqual(response["status"], "not_enrolled")
        self.assertEqual(response["message"], "Sinh viên không thuộc danh sách lớp học phần này")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].student_id, student.id)
        self.assertEqual(self.attendance_count(), 0)

    def test_enrolled_student_outside_window_creates_late_entry_alert_without_attendance(self):
        student, session = self.add_enrolled_session()
        self.patch_now(datetime(2026, 6, 1, 7, 41))

        response = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            confidence=0.91,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            recognition_status="success",
        )

        alerts = self.alerts("LATE_ENTRY")
        self.assertEqual(response["status"], "expired")
        self.assertEqual(response["message"], "Lớp học đã kết thúc điểm danh")
        self.assertEqual(len(alerts), 1)
        self.assertEqual(alerts[0].student_id, student.id)
        self.assertEqual(self.attendance_count(), 0)

    def test_enrolled_student_inside_window_creates_attendance(self):
        student, session = self.add_enrolled_session()
        self.patch_now(datetime(2026, 6, 1, 7, 31))

        response = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            confidence=0.91,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            recognition_status="success",
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["student_code"], student.student_code)
        self.assertEqual(self.attendance_count(), 1)
        self.assertEqual(len(self.alerts()), 0)

    def test_uncertain_enrolled_student_proceeds_without_manual_flow(self):
        student, session = self.add_enrolled_session()
        self.patch_now(datetime(2026, 6, 1, 7, 31))

        response = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            confidence=0.65,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            recognition_status="uncertain",
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["data"]["status"], "present")
        self.assertEqual(self.attendance_count(), 1)
        self.assertEqual(len(self.alerts()), 0)


if __name__ == "__main__":
    unittest.main()
