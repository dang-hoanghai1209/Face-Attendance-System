import os
import asyncio
import csv
import io
import json
import unittest
from datetime import date, datetime, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_TIMEZONE", "Asia/Nha_Trang")

from fastapi import HTTPException

from database import Base, SessionLocal, engine
from models.attendance import Attendance
from models.attendance_scan import AttendanceScan
from models.classroom import Classroom
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.security_alert import SecurityAlert
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
from routes import reports
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

    def add_session_enrollments(self, session, students):
        for student in students:
            if session.section_id:
                exists = (
                    self.db.query(Enrollment)
                    .filter(Enrollment.course_section_id == session.section_id, Enrollment.student_id == student.id)
                    .first()
                )
                if not exists:
                    self.db.add(Enrollment(course_section_id=session.section_id, student_id=student.id, status="active"))
            else:
                exists = (
                    self.db.query(Enrollment)
                    .filter(Enrollment.session_id == session.id, Enrollment.student_id == student.id)
                    .first()
                )
                if not exists:
                    self.db.add(Enrollment(session_id=session.id, student_id=student.id, status="active"))
        self.db.commit()

    def collect_streaming_response(self, response):
        async def collect():
            chunks = []
            async for chunk in response.body_iterator:
                chunks.append(chunk if isinstance(chunk, bytes) else chunk.encode())
            return b"".join(chunks)

        return asyncio.run(collect())

    def add_min_session_enrollments(self, session, student, total=5):
        students = [student]
        for index in range(1, total):
            students.append(
                self.add_student(
                    student_code=f"{student.student_code}E{session.id}{index}",
                    full_name=f"Enrollment Student {index}",
                    class_name=student.class_name,
                )
            )
        self.add_session_enrollments(session, students)

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
            class_name="64CNTT",
            subject_id=subject.id,
            status="open",
        )
        self.db.add(section)
        self.db.commit()
        self.db.refresh(section)

        session = ClassSession(
            subject=subject.subject_name,
            class_name=section.class_name,
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
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
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

    def test_checkin_creates_attendance_scan_and_updates_scan_fields(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
        scanned_at = datetime(2026, 5, 30, 7, 31)
        self.patch_now(scanned_at)

        response = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            confidence=0.91,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            liveness_passed=True,
        )
        record = self.db.query(Attendance).filter(Attendance.id == response["data"]["record_id"]).first()
        scans = self.db.query(AttendanceScan).filter(AttendanceScan.attendance_id == record.id).all()

        self.assertEqual(record.scan_count, 1)
        self.assertEqual(record.last_scan_at, scanned_at)
        self.assertEqual(len(scans), 1)
        self.assertEqual(scans[0].scan_index, 1)
        self.assertEqual(scans[0].confidence, 0.91)
        self.assertEqual(scans[0].gps_lat, session.latitude)
        self.assertEqual(scans[0].gps_lng, session.longitude)
        self.assertTrue(scans[0].liveness_passed)
        self.assertEqual(scans[0].note, "check_in")

    def test_export_session_csv_returns_utf8_bom_and_attendance_columns(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
        self.patch_now(datetime(2026, 5, 30, 7, 31))
        response_data = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            confidence=0.91,
            image_path="media/captures/checkin.jpg",
            gps_lat=session.latitude,
            gps_lng=session.longitude,
            gps_accuracy=8.5,
            liveness_passed=True,
        )
        record = self.db.query(Attendance).filter(Attendance.id == response_data["data"]["record_id"]).first()
        record.note = "checked by camera"
        self.db.commit()

        user = type("User", (), {"role": "admin"})()
        response = reports.export_session_csv(session.id, current_user=user, db=self.db)
        body = self.collect_streaming_response(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.media_type)
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertTrue(body.startswith(b"\xef\xbb\xbf"))
        csv_text = body.decode("utf-8-sig")
        self.assertIn("session_id,class_name,student_code,full_name,attendance_status", csv_text.splitlines()[0])
        self.assertIn("liveness_passed", csv_text.splitlines()[0])
        self.assertIn("gps_lat", csv_text.splitlines()[0])
        self.assertIn("check_in_img", csv_text.splitlines()[0])
        self.assertIn(student.student_code, csv_text)
        self.assertIn("checked by camera", csv_text)

    def test_export_session_alerts_csv_parses_json_reason_code_and_handles_text_note(self):
        student = self.add_student()
        session = self.add_session()
        self.add_session_enrollments(session, [student])
        json_alert = SecurityAlert(
            session_id=session.id,
            alert_type="FACE_UNCLEAR",
            student_id=student.id,
            captured_img="media/security_snapshots/1/face.jpg",
            confidence=0.88,
            liveness_score=0.77,
            gps_lat=12.1,
            gps_lng=109.1,
            note=json.dumps({"reason_code": "LOW_SHARPNESS", "quality": {"sharpness": 2.0}}),
        )
        text_alert = SecurityAlert(
            session_id=session.id,
            alert_type="UNKNOWN_FACE",
            captured_img="media/alerts/1/unknown.jpg",
            confidence=0.41,
            note="plain text note",
        )
        self.db.add_all([json_alert, text_alert])
        self.db.commit()

        user = type("User", (), {"role": "admin"})()
        response = reports.export_session_alerts_csv(session.id, current_user=user, db=self.db)
        body = self.collect_streaming_response(response)

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/csv", response.media_type)
        self.assertIn("attachment", response.headers["content-disposition"])
        self.assertTrue(body.startswith(b"\xef\xbb\xbf"))
        csv_text = body.decode("utf-8-sig")
        header = csv_text.splitlines()[0]
        self.assertIn("alert_id,session_id,alert_type,reason_code", header)
        self.assertIn("confidence_label", header)
        rows = list(csv.DictReader(io.StringIO(csv_text)))
        by_type = {row["alert_type"]: row for row in rows}
        self.assertEqual(by_type["FACE_UNCLEAR"]["reason_code"], "LOW_SHARPNESS")
        self.assertEqual(by_type["FACE_UNCLEAR"]["confidence_label"], "Độ tin cậy phát hiện khuôn mặt")
        self.assertEqual(by_type["UNKNOWN_FACE"]["reason_code"], "")
        self.assertEqual(by_type["UNKNOWN_FACE"]["note"], "plain text note")
        self.assertEqual(by_type["UNKNOWN_FACE"]["confidence_label"], "Độ tin cậy khớp danh tính")

    def test_export_session_csv_rejects_student_role(self):
        student = self.add_student()
        session = self.add_session()
        self.add_session_enrollments(session, [student])

        user = type("User", (), {"role": "student", "username": student.student_code})()

        with self.assertRaises(HTTPException) as context:
            reports.export_session_csv(session.id, current_user=user, db=self.db)

        self.assertEqual(context.exception.status_code, 403)

    def test_export_session_alerts_csv_rejects_student_role(self):
        student = self.add_student()
        session = self.add_session()
        self.add_session_enrollments(session, [student])
        self.db.add(SecurityAlert(session_id=session.id, alert_type="UNKNOWN_FACE", note="private alert"))
        self.db.commit()

        user = type("User", (), {"role": "student", "username": student.student_code})()

        with self.assertRaises(HTTPException) as context:
            reports.export_session_alerts_csv(session.id, current_user=user, db=self.db)

        self.assertEqual(context.exception.status_code, 403)

    def test_export_session_csv_rejects_teacher_without_session_scope(self):
        student = self.add_student()
        session = self.add_session()
        self.add_session_enrollments(session, [student])

        user = type("User", (), {"role": "teacher", "username": "other_teacher", "full_name": "Other Teacher"})()

        with self.assertRaises(HTTPException) as context:
            reports.export_session_csv(session.id, current_user=user, db=self.db)

        self.assertEqual(context.exception.status_code, 403)

    def test_export_session_csv_returns_header_for_empty_session(self):
        session = self.add_session()
        user = type("User", (), {"role": "admin"})()

        response = reports.export_session_csv(session.id, current_user=user, db=self.db)
        body = self.collect_streaming_response(response)

        self.assertEqual(response.status_code, 200)
        self.assertTrue(body.startswith(b"\xef\xbb\xbf"))
        rows = body.decode("utf-8-sig").splitlines()
        self.assertEqual(len(rows), 1)
        self.assertIn("session_id,class_name,student_code,full_name,attendance_status", rows[0])
        self.assertIn("filename=attendance_session_", response.headers["content-disposition"])

    def test_export_session_csv_returns_404_for_missing_session(self):
        user = type("User", (), {"role": "admin"})()

        with self.assertRaises(HTTPException) as context:
            reports.export_session_csv(999999, current_user=user, db=self.db)

        self.assertEqual(context.exception.status_code, 404)

    def test_repeat_checkin_returns_already_checked_in_without_changing_status(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)

        self.patch_now(datetime(2026, 5, 30, 7, 31))
        first = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            confidence=0.91,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
        )
        self.assertEqual(first["data"]["status"], "present")
        self.restore_now()

        self.patch_now(datetime(2026, 5, 30, 7, 34))
        second = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            confidence=0.88,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
        )
        self.assertEqual(second["status"], "already_checked_in")
        self.assertEqual(second["data"]["status"], "present")
        self.restore_now()

        self.patch_now(datetime(2026, 5, 30, 7, 36))
        third = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            confidence=0.93,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
        )

        record = self.db.query(Attendance).filter(Attendance.id == third["data"]["record_id"]).first()
        scans = (
            self.db.query(AttendanceScan)
            .filter(AttendanceScan.attendance_id == record.id)
            .order_by(AttendanceScan.scan_index.asc())
            .all()
        )
        self.assertEqual(third["status"], "already_checked_in")
        self.assertEqual(third["data"]["status"], "present")
        self.assertEqual(record.status, "present")
        self.assertEqual(record.scan_count, 3)
        self.assertEqual([scan.scan_index for scan in scans], [1, 2, 3])
        self.assertEqual([scan.note for scan in scans], ["check_in", "already_checked_in", "already_checked_in"])

    def test_manual_attendance_service_is_removed(self):
        self.assertFalse(hasattr(attendance_service, "record_manual_attendance"))

    def test_manual_student_defaults_to_real_source(self):
        student = Student(student_code="63133870", full_name="Nguyen Van A", class_name="63HTTT")
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)

        self.assertEqual(student.data_source, "real")
        self.assertFalse(student.is_demo)
        self.assertIsNone(student.registration_method)

    def test_checkin_late(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
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
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
        self.patch_now(datetime(2026, 5, 30, 7, 41))

        response = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
        )

        self.assertEqual(response["status"], "expired")
        self.assertEqual(response["message"], "Lớp học đã kết thúc điểm danh")
        self.assertEqual(response["alert_type"], "LATE_ENTRY")
        self.assertEqual(self.db.query(Attendance).count(), 0)

    def test_checkin_rejects_before_attendance_window(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
        self.patch_now(datetime(2026, 5, 30, 7, 14))

        response = attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

        self.assertEqual(response["status"], "not_started")
        self.assertEqual(response["message"], "Lớp học chưa bắt đầu điểm danh")
        self.assertEqual(response["alert_type"], "LATE_ENTRY")
        self.assertEqual(self.db.query(Attendance).count(), 0)

    def test_checkin_boundary_allows_15_minutes_before_start(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
        self.patch_now(datetime(2026, 5, 30, 7, 15))

        response = attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

        self.assertEqual(response["status"], "success")
        self.assertEqual(self.db.query(Attendance).count(), 1)

    def test_checkin_boundary_allows_10_minutes_after_start(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
        self.patch_now(datetime(2026, 5, 30, 7, 40))

        response = attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

        self.assertEqual(response["status"], "success")
        self.assertEqual(self.db.query(Attendance).count(), 1)

    def test_checkin_rejects_session_with_less_than_minimum_enrollments(self):
        student = self.add_student()
        session = self.add_session()
        self.add_session_enrollments(session, [student])
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_checkin(
                self.db,
                student.student_code,
                session.id,
                gps_lat=session.latitude,
                gps_lng=session.longitude,
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["status"], "insufficient_enrollments")
        self.assertEqual(ctx.exception.detail["message"], attendance_service.MIN_SESSION_ENROLLMENTS_MESSAGE)
        self.assertEqual(ctx.exception.detail["enrollment_count"], 1)
        self.assertEqual(ctx.exception.detail["minimum_required"], attendance_service.MIN_SESSION_ENROLLMENTS)

    def test_checkin_allows_session_with_at_least_five_enrollments(self):
        student = self.add_student()
        extra_students = [
            self.add_student(student_code=f"6313390{index}", full_name=f"Student {index}")
            for index in range(1, 5)
        ]
        session = self.add_session()
        self.add_session_enrollments(session, [student, *extra_students])
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        response = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            gps_lat=session.latitude,
            gps_lng=session.longitude,
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["student_code"], student.student_code)

    def test_section_session_requires_active_enrollment(self):
        self.add_student()
        _section, classroom, session = self.add_section_session()
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        response = attendance_service.record_checkin(
            self.db,
            "63133870",
            session.id,
            gps_lat=classroom.gps_lat,
            gps_lng=classroom.gps_lng,
        )

        self.assertEqual(response["status"], "not_enrolled")
        self.assertEqual(response["alert_type"], "NOT_ENROLLED")
        self.assertEqual(response["message"], "Sinh viên không thuộc danh sách lớp học phần này")

    def test_section_session_rejects_same_class_student_without_section_enrollment(self):
        student = self.add_student(class_name="64CNTT")
        section, classroom, session = self.add_section_session()
        other_students = [
            self.add_student(student_code=f"6400000{index}", full_name=f"Section Student {index}", class_name="64CNTT")
            for index in range(1, 6)
        ]
        self.add_session_enrollments(session, other_students)
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        response = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            gps_lat=classroom.gps_lat,
            gps_lng=classroom.gps_lng,
        )

        self.assertEqual(section.id, session.section_id)
        self.assertEqual(response["status"], "not_enrolled")
        self.assertEqual(response["alert_type"], "NOT_ENROLLED")
        self.assertEqual(response["message"], "Sinh viên không thuộc danh sách lớp học phần này")
        self.assertEqual(self.db.query(Attendance).count(), 0)

    def test_section_session_allows_different_class_student_with_section_enrollment(self):
        student = self.add_student(class_name="63CNTT")
        section, classroom, session = self.add_section_session()
        self.add_min_session_enrollments(session, student)
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        response = attendance_service.record_checkin(
            self.db,
            student.student_code,
            session.id,
            gps_lat=classroom.gps_lat,
            gps_lng=classroom.gps_lng,
        )

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["student_code"], student.student_code)
        self.assertEqual(self.db.query(Attendance).count(), 1)

    def test_session_report_excludes_attendance_outside_section_enrollment(self):
        enrolled = self.add_student(student_code="64000001", full_name="Enrolled Student", class_name="64CNTT")
        outsider = self.add_student(student_code="64000002", full_name="Outside Student", class_name="64CNTT")
        _section, _classroom, session = self.add_section_session()
        self.add_min_session_enrollments(session, enrolled)
        self.db.add(Attendance(student_id=outsider.id, session_id=session.id, status="present"))
        self.db.commit()

        _session, rows = report_service.build_session_report(session.id, self.db)
        by_code = {row["student_code"]: row for row in rows}

        self.assertIn(enrolled.student_code, by_code)
        self.assertNotIn(outsider.student_code, by_code)

    def test_section_session_saves_gps_when_valid(self):
        student = self.add_student()
        section, classroom, session = self.add_section_session()
        self.db.add(Enrollment(course_section_id=section.id, student_id=student.id, status="active"))
        self.db.commit()
        self.add_min_session_enrollments(session, student)
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
        self.add_min_session_enrollments(session, student)
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
        self.assertEqual(ctx.exception.detail["message"], "Ngoài phạm vi điểm danh")

    def test_checkin_rejects_session_without_gps_configuration(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
        session.latitude = None
        session.longitude = None
        self.db.commit()
        self.patch_now(datetime(2026, 5, 30, 7, 35))

        with self.assertRaises(Exception) as ctx:
            attendance_service.record_checkin(
                self.db,
                "63133870",
                session.id,
                gps_lat=12.238912,
                gps_lng=109.196748,
            )

        self.assertEqual(ctx.exception.status_code, 403)
        self.assertEqual(ctx.exception.detail["status"], "session_gps_missing")
        self.assertEqual(ctx.exception.detail["message"], "Buổi học chưa cấu hình tọa độ GPS")

    def test_checkout_updates_existing_record(self):
        student = self.add_student()
        session = self.add_session()
        self.add_min_session_enrollments(session, student)
        self.patch_now(datetime(2026, 5, 30, 7, 35))
        attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)
        self.patch_now(datetime(2026, 5, 30, 9, 25))

        response = attendance_service.record_checkout(self.db, "63133870", session.id, confidence=0.88)

        self.assertIsNotNone(response["data"]["check_out_at"])
        self.assertEqual(response["data"]["check_out_conf"], 0.88)

    def test_attendance_statuses_do_not_include_manual(self):
        self.assertNotIn("manual", attendance_service.ATTENDED_STATUSES)

    def test_session_report_marks_absent_student(self):
        present_student = self.add_student("63133870", "Nguyen Van A")
        self.add_student("63133871", "Tran Van B")
        session = self.add_session()
        self.add_min_session_enrollments(session, present_student)
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

    def test_delete_attendance_record_removes_scan_logs(self):
        student = self.add_student()
        session = self.add_session()
        record = Attendance(student_id=student.id, session_id=session.id, status="present")
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)
        scan = AttendanceScan(
            attendance_id=record.id,
            scanned_at=datetime(2026, 5, 30, 7, 31),
            scan_index=1,
            confidence=0.91,
        )
        self.db.add(scan)
        self.db.commit()

        response = attendance_service.delete_attendance_record(self.db, record.id)

        self.assertEqual(response["status"], "success")
        self.assertIsNone(self.db.query(Attendance).filter(Attendance.id == record.id).first())
        self.assertEqual(
            self.db.query(AttendanceScan).filter(AttendanceScan.attendance_id == record.id).count(),
            0,
        )

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

    def test_left_early_counts_as_attended_in_class_summary(self):
        student = self.add_student()
        session = self.add_session()
        self.db.add(Attendance(student_id=student.id, session_id=session.id, status="left_early"))
        self.db.commit()

        summary = report_service.build_class_summary("63HTTT", self.db)

        self.assertEqual(summary[0]["attended"], 1)
        self.assertEqual(summary[0]["absent"], 0)
        self.assertEqual(summary[0]["rate"], 1.0)

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

    def test_unregistered_real_student_cannot_check_in_officially(self):
        self.add_student(face_status="unregistered", registration_method=None)
        session = self.add_session()

        with self.assertRaisesRegex(Exception, "chưa đăng ký khuôn mặt"):
            attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

    def test_cross_class_student_returns_not_enrolled_without_manual_confirmation(self):
        self.add_student(student_code="63133870", class_name="63TTQL")
        session = self.add_session(class_name="64TTQL")

        response = attendance_service.record_checkin(self.db, "63133870", session.id, gps_lat=session.latitude, gps_lng=session.longitude)

        self.assertEqual(response["status"], "not_enrolled")
        self.assertEqual(response["alert_type"], "NOT_ENROLLED")
        self.assertEqual(response["message"], "Sinh viên không thuộc danh sách lớp học phần này")
        self.assertEqual(self.db.query(Attendance).count(), 0)


if __name__ == "__main__":
    unittest.main()
