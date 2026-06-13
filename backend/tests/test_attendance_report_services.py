import os
import unittest
from datetime import date, datetime, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_TIMEZONE", "Asia/Nha_Trang")

from database import Base, SessionLocal, engine
from models.attendance import Attendance
from models.classroom import Classroom
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.recognition_attempt import RecognitionAttempt
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
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
            latitude=12.238912,
            longitude=109.196748,
            radius_meters=20,
            session_date=date(2026, 5, 30),
            start_time=start_time,
            end_time=time(9, 30),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def add_section_session(self):
        classroom = Classroom(
            name="Room 101",
            gps_lat=12.238912,
            gps_lng=109.196748,
            radius_meters=20,
            is_active=True,
        )
        subject = Subject(subject_code="MVP101", subject_name="MVP Subject")
        self.db.add_all([classroom, subject])
        self.db.commit()
        self.db.refresh(classroom)
        self.db.refresh(subject)

        section = CourseSection(
            section_code="MVP101-64CNTT-2026",
            subject_id=subject.id,
            status="open",
        )
        self.db.add(section)
        self.db.commit()
        self.db.refresh(section)

        session = ClassSession(
            subject=subject.subject_name,
            class_name=section.section_code,
            section_id=section.id,
            classroom_id=classroom.id,
            latitude=classroom.gps_lat,
            longitude=classroom.gps_lng,
            radius_meters=classroom.radius_meters,
            room_name=classroom.name,
            session_date=date(2026, 5, 30),
            start_time=time(7, 30),
            end_time=time(9, 30),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return section, classroom, session

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
        self.patch_now(datetime(2026, 5, 30, 7, 31))

        response = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            confidence=0.91,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
        )

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
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        response = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
        )

        self.assertEqual(response["data"]["status"], "late")

    def test_checkin_rejects_after_attendance_deadline(self):
        self.add_student()
        session = self.add_session()
        self.patch_now(datetime(2026, 5, 30, 7, 41))

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_checkin(
                self.db,
                "63133870",
                session.id,
                gps_lat=session.latitude,
                gps_lng=session.longitude,
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["status"], "attendance_closed")
        self.assertIn("Đã quá thời gian điểm danh", ctx.exception.detail["message"])

    def test_checkin_rejects_before_session_start(self):
        self.add_student()
        session = self.add_session()
        self.patch_now(datetime(2026, 5, 30, 7, 24))

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

        self.assertEqual(ctx.exception.status_code, 400)
        self.assertEqual(ctx.exception.detail["status"], "not_started")
        self.assertIn("Buổi học chưa bắt đầu", ctx.exception.detail["message"])

    def test_section_session_requires_active_enrollment(self):
        self.add_student()
        _section, classroom, session = self.add_section_session()
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_checkin(
                self.db,
                "63133870",
                session.id,
                gps_lat=classroom.gps_lat,
                gps_lng=classroom.gps_lng,
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["status"], "not_enrolled")
        self.assertEqual(ctx.exception.detail["message"], "Bạn không có trong danh sách đăng ký của lớp học phần này.")

    def test_section_session_saves_gps_when_valid(self):
        student = self.add_student()
        section, classroom, session = self.add_section_session()
        self.db.add(Enrollment(course_section_id=section.id, student_id=student.id, status="active"))
        self.db.commit()
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        response = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            confidence=0.91,
            gps_lat=classroom.gps_lat,
            gps_lng=classroom.gps_lng,
            gps_accuracy=5.5,
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["message"], "Điểm danh thành công.")
        self.assertEqual(response["student_code"], "63133870")
        self.assertEqual(response["full_name"], "Nguyen Van A")
        self.assertEqual(response["confidence"], 0.91)
        self.assertEqual(response["data"]["gps_accuracy"], 5.5)
        self.assertEqual(response["data"]["distance_meters"], 0.0)
        self.assertEqual(response["distance_meters"], 0.0)
        self.assertEqual(response["allowed_radius_meters"], classroom.radius_meters)
        self.assertIsNotNone(response["check_in_time"])

    def test_section_session_rejects_gps_out_of_range(self):
        student = self.add_student()
        section, _classroom, session = self.add_section_session()
        self.db.add(Enrollment(course_section_id=section.id, student_id=student.id, status="active"))
        self.db.commit()
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_checkin(
                self.db,
                "63133870",
                session.id,
                gps_lat=13.0,
                gps_lng=109.0,
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["status"], "gps_out_of_range")
        self.assertEqual(ctx.exception.detail["message"], "Ngoài phạm vi lớp học")

    def test_checkout_updates_existing_record(self):
        self.add_student()
        session = self.add_session()
        self.patch_now(datetime(2026, 5, 30, 7, 35))
        attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)
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
        self.patch_now(datetime(2026, 5, 30, 7, 31))
        checkin_response = attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

        _session, rows = report_service.build_session_report(session.id, self.db)
        by_code = {row["student_code"]: row for row in rows}

        self.assertEqual(by_code["63133870"]["status"], "present")
        self.assertEqual(by_code["63133870"]["record_id"], checkin_response["data"]["record_id"])
        self.assertEqual(by_code["63133871"]["status"], "absent")
        self.assertIsNone(by_code["63133871"]["record_id"])

    def test_delete_attendance_record_removes_only_target_record(self):
        first_student = self.add_student("63133870", "Nguyen Van A")
        second_student = self.add_student("63133871", "Tran Van B")
        session = self.add_session()
        other_session = self.add_session()
        target = Attendance(student_id=first_student.id, session_id=session.id, status="present")
        other_student_record = Attendance(student_id=second_student.id, session_id=session.id, status="present")
        other_session_record = Attendance(student_id=first_student.id, session_id=other_session.id, status="present")
        self.db.add_all([target, other_student_record, other_session_record])
        self.db.commit()
        self.db.refresh(target)
        self.db.refresh(other_student_record)
        self.db.refresh(other_session_record)

        response = attendance_service.delete_attendance_record(self.db, target.id)

        self.assertEqual(response["status"], "success")
        self.assertIsNone(self.db.query(Attendance).filter(Attendance.id == target.id).first())
        self.assertIsNotNone(self.db.query(Attendance).filter(Attendance.id == other_student_record.id).first())
        self.assertIsNotNone(self.db.query(Attendance).filter(Attendance.id == other_session_record.id).first())
        _session, rows = report_service.build_session_report(session.id, self.db)
        by_code = {row["student_code"]: row for row in rows}
        self.assertEqual(by_code["63133870"]["status"], "absent")
        self.assertEqual(by_code["63133871"]["status"], "present")

    def test_delete_attendance_record_returns_clear_404(self):
        with self.assertRaises(Exception) as ctx:
            attendance_service.delete_attendance_record(self.db, 999)

        self.assertEqual(ctx.exception.status_code, 404)
        self.assertEqual(ctx.exception.detail["reason"], "attendance_record_not_found")

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
            attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

    def test_demo_student_cannot_be_manually_attended_officially(self):
        self.add_student(data_source="kaggle", is_demo=True, registration_method="import")
        session = self.add_session()

        with self.assertRaisesRegex(Exception, "demo/Kaggle"):
            attendance_service.record_manual_attendance(self.db, "63133870", session.id)

    def test_unregistered_real_student_cannot_check_in_officially(self):
        self.add_student(face_status="unregistered", registration_method=None)
        session = self.add_session()

        with self.assertRaisesRegex(Exception, "chưa đăng ký khuôn mặt"):
            attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

    def test_cross_class_student_requires_manual_confirmation_message(self):
        self.add_student(student_code="63133870", class_name="63TTQL")
        session = self.add_session(class_name="64TTQL")

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

        detail = ctx.exception.detail
        self.assertEqual(detail["code"], "cross_class_requires_manual_confirmation")
        self.assertEqual(detail["reason"], "class_mismatch")
        self.assertIn("Sinh viên thuộc lớp 63TTQL, khác lớp chính của buổi học 64TTQL", detail["message"])


    def test_cross_class_manual_attendance_requires_recognition_audit(self):
        self.add_student(student_code="63133870", class_name="63TTQL")
        session = self.add_session(class_name="64TTQL")

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_manual_attendance(self.db, "63133870", session.id)

        self.assertEqual(ctx.exception.detail["reason"], "missing_recognition_audit")

    def test_cross_class_manual_attendance_with_valid_audit_creates_record(self):
        student = self.add_student(student_code="63133870", class_name="63TTQL")
        session = self.add_session(class_name="64TTQL")
        attempt = RecognitionAttempt(
            session_id=session.id,
            predicted_student_id=student.id,
            predicted_student_code=student.student_code,
            confidence=0.91,
            status="class_mismatch",
            message="class mismatch",
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)

        response = attendance_service.record_manual_attendance(
            self.db,
            "63133870",
            session.id,
            note="Teacher confirmed cross-class student",
            audit_id=attempt.id,
        )

        self.assertEqual(response["data"]["status"], "manual")
        self.assertEqual(response["data"]["check_in_conf"], 0.91)
        _session, rows = report_service.build_session_report(session.id, self.db)
        by_code = {row["student_code"]: row for row in rows}
        self.assertEqual(by_code["63133870"]["status"], "manual")

    def test_cross_class_manual_attendance_accepts_legacy_success_audit(self):
        student = self.add_student(student_code="63133870", class_name="63TTQL")
        session = self.add_session(class_name="64TTQL")
        attempt = RecognitionAttempt(
            session_id=session.id,
            predicted_student_id=student.id,
            predicted_student_code=student.student_code,
            confidence=0.89,
            status="success",
            message="legacy recognized audit before class_mismatch status was stored",
        )
        self.db.add(attempt)
        self.db.commit()
        self.db.refresh(attempt)

        response = attendance_service.record_manual_attendance(
            self.db,
            "63133870",
            session.id,
            audit_id=attempt.id,
        )

        self.assertEqual(response["data"]["status"], "manual")
        self.assertEqual(response["data"]["check_in_conf"], 0.89)
        _session, rows = report_service.build_session_report(session.id, self.db)
        by_code = {row["student_code"]: row for row in rows}
        self.assertEqual(by_code["63133870"]["status"], "manual")


if __name__ == "__main__":
    unittest.main()
