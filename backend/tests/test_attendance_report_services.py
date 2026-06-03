import os
import unittest
from datetime import date, datetime, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_TIMEZONE", "Asia/Nha_Trang")

from database import Base, SessionLocal, engine
from models.attendance import Attendance
from models.session import Session as ClassSession
from models.student import Student
from services import attendance_service, report_service
from services import timezone_service


class AttendanceReportServiceTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def add_student(
        self,
        student_code="63133870",
        full_name="Nguyen Van A",
        class_name="63HTTT",
        face_status="registered",
        data_source="real",
        is_demo=False,
        registration_method="camera",
    ):
        student = Student(
            student_code=student_code,
            full_name=full_name,
            class_name=class_name,
            face_status=face_status,
            data_source=data_source,
            is_demo=is_demo,
            registration_method=registration_method,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def add_session(self, class_name="63HTTT", start_time=time(7, 30)):
        session = ClassSession(
            subject="AI",
            class_name=class_name,
            session_date=date(2026, 5, 30),
            start_time=start_time,
            end_time=time(9, 30),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def patch_now(self, value):
        self.original_now = attendance_service.now_in_app_timezone
        attendance_service.now_in_app_timezone = lambda: value
        self.addCleanup(self.restore_now)

    def restore_now(self):
        if hasattr(self, "original_now"):
            attendance_service.now_in_app_timezone = self.original_now
            del self.original_now

    def test_checkin_on_time(self):
        self.add_student()
        session = self.add_session()
        self.patch_now(datetime(2026, 5, 30, 7, 40))

        response = attendance_service.record_checkin(self.db, "63133870", session.id, confidence=0.91)

        self.assertEqual(response["data"]["status"], "present")
        self.assertEqual(response["data"]["check_in_conf"], 0.91)

    def test_manual_student_defaults_to_real_source(self):
        student = Student(student_code="63133870", full_name="Nguyen Van A", class_name="63HTTT")
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        self.assertEqual(student.data_source, "real")
        self.assertFalse(student.is_demo)
        self.assertIsNone(student.registration_method)

    def test_checkin_late(self):
        self.add_student()
        session = self.add_session()
        self.patch_now(datetime(2026, 5, 30, 7, 46))

        response = attendance_service.record_checkin(self.db, "63133870", session.id)

        self.assertEqual(response["data"]["status"], "late")

    def test_checkout_updates_existing_record(self):
        self.add_student()
        session = self.add_session()
        self.patch_now(datetime(2026, 5, 30, 7, 35))
        attendance_service.record_checkin(self.db, "63133870", session.id)
        self.patch_now(datetime(2026, 5, 30, 9, 25))

        response = attendance_service.record_checkout(self.db, "63133870", session.id, confidence=0.88)

        self.assertIsNotNone(response["data"]["check_out_at"])
        self.assertEqual(response["data"]["check_out_conf"], 0.88)

    def test_manual_creates_manual_record(self):
        self.add_student()
        session = self.add_session()
        self.patch_now(datetime(2026, 5, 30, 8, 0))

        response = attendance_service.record_manual_attendance(self.db, "63133870", session.id, note="Teacher confirmed")

        self.assertEqual(response["data"]["status"], "manual")
        self.assertEqual(response["data"]["note"], "Teacher confirmed")

    def test_session_report_marks_absent_student(self):
        self.add_student("63133870", "Nguyen Van A")
        self.add_student("63133871", "Tran Van B")
        session = self.add_session()
        self.patch_now(datetime(2026, 5, 30, 7, 35))
        attendance_service.record_checkin(self.db, "63133870", session.id)

        _session, rows = report_service.build_session_report(session.id, self.db)
        by_code = {row["student_code"]: row for row in rows}

        self.assertEqual(by_code["63133870"]["status"], "present")
        self.assertEqual(by_code["63133871"]["status"], "absent")

    def test_duplicate_attendance_counts_once_in_summary(self):
        first = Attendance(id=1, student_id=1, session_id=1, status="present")
        duplicate = Attendance(id=2, student_id=1, session_id=1, status="late")

        records = report_service.best_records_by([first, duplicate], "session_id")

        self.assertEqual(len(records), 1)
        self.assertIs(records[1], first)

    def test_dashboard_ignores_cross_class_attendance(self):
        student = self.add_student(class_name="63HTTT")
        self.add_session(class_name="63HTTT")
        other_class_session = self.add_session(class_name="64HTTT")
        self.db.add(Attendance(student_id=student.id, session_id=other_class_session.id, status="present"))
        self.db.commit()

        stats = report_service.get_dashboard_stats(self.db)

        self.assertEqual(stats["pie_data"][0]["value"], 0)
        self.assertEqual(stats["pie_data"][1]["value"], 1)
        self.assertEqual(stats["avg_attendance_rate"], 0)

    def test_reports_exclude_demo_students_and_legacy_demo_attendance(self):
        real_student = self.add_student("63133870", "Real Student")
        demo_student = self.add_student(
            "63133871",
            "Kaggle Sample",
            data_source="kaggle",
            is_demo=True,
            registration_method="import",
        )
        session = self.add_session()
        self.db.add(Attendance(student_id=real_student.id, session_id=session.id, status="present"))
        self.db.add(Attendance(student_id=demo_student.id, session_id=session.id, status="present"))
        self.db.commit()

        summary = report_service.build_class_summary("63HTTT", self.db)
        _session, rows = report_service.build_session_report(session.id, self.db)
        stats = report_service.get_dashboard_stats(self.db)

        self.assertEqual([row["student_code"] for row in summary], ["63133870"])
        self.assertEqual([row["student_code"] for row in rows], ["63133870"])
        self.assertEqual(stats["total_students"], 1)
        self.assertEqual(stats["pie_data"][0]["value"], 1)

    def test_nha_trang_timezone_alias_resolves_to_vietnam_timezone(self):
        self.assertEqual(
            timezone_service.resolved_timezone_name("Asia/Nha_Trang"),
            "Asia/Ho_Chi_Minh",
        )

    def test_demo_student_cannot_check_in_officially(self):
        self.add_student(data_source="kaggle", is_demo=True, registration_method="import")
        session = self.add_session()

        with self.assertRaisesRegex(Exception, "demo/Kaggle"):
            attendance_service.record_checkin(self.db, "63133870", session.id)

    def test_demo_student_cannot_be_manually_attended_officially(self):
        self.add_student(data_source="kaggle", is_demo=True, registration_method="import")
        session = self.add_session()

        with self.assertRaisesRegex(Exception, "demo/Kaggle"):
            attendance_service.record_manual_attendance(self.db, "63133870", session.id)

    def test_unregistered_real_student_cannot_check_in_officially(self):
        self.add_student(face_status="unregistered", registration_method=None)
        session = self.add_session()

        with self.assertRaisesRegex(Exception, "chưa đăng ký khuôn mặt"):
            attendance_service.record_checkin(self.db, "63133870", session.id)

    def test_cross_class_student_requires_manual_confirmation_message(self):
        self.add_student(student_code="63133870", class_name="63TTQL")
        session = self.add_session(class_name="64TTQL")

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_checkin(self.db, "63133870", session.id)

        detail = ctx.exception.detail
        self.assertEqual(detail["code"], "cross_class_requires_manual_confirmation")
        self.assertEqual(detail["reason"], "class_mismatch")
        self.assertIn("Sinh viên thuộc lớp 63TTQL, khác lớp chính của buổi học 64TTQL", detail["message"])


if __name__ == "__main__":
    unittest.main()
