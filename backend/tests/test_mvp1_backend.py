import os
import json
import unittest
from datetime import date, datetime, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_TIMEZONE", "Asia/Nha_Trang")

from database import Base, SessionLocal, engine
from models.attendance import Attendance
from models.classroom import Classroom
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
from routes.classrooms import ClassroomCreate, create_classroom
from routes.attendance import AttendanceCheckIn, _checkin_response
from routes.course_sections import CourseSectionCreate, create_course_section, get_course_section_students
from routes.enrollments import EnrollmentCreate, create_enrollment, delete_enrollment, get_student_enrollments
from routes.sessions import SessionFromSectionCreate, create_session_from_section
from routes.students import _mobile_session_status, get_my_active_sessions
from routes.subjects import SubjectCreate, create_subject
from services import attendance_service, report_service


class BackendMVP1Tests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def add_student(self, code="64100001", class_name="64CNTT", name="Test Student"):
        student = Student(
            student_code=code,
            full_name=name,
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

    def add_section_bundle(self):
        classroom = create_classroom(
            ClassroomCreate(
                name="Phòng A101",
                building="Khu A",
                gps_lat=12.238912,
                gps_lng=109.196748,
                radius_meters=20,
            ),
            _current_user=None,
            db=self.db,
        )
        subject = create_subject(
            SubjectCreate(subject_code="MVP101", subject_name="MVP Subject", credits=3, department="CNTT"),
            _current_user=None,
            db=self.db,
        )
        section = create_course_section(
            CourseSectionCreate(
                section_code="MVP101-64CNTT-2026",
                subject_id=subject.id,
                semester="2026-1",
                academic_year="2025-2026",
                lecturer_name="Giảng viên MVP",
                status="open",
            ),
            _current_user=None,
            db=self.db,
        )
        return classroom, subject, section

    def test_haversine_distance_is_zero_for_same_point(self):
        self.assertAlmostEqual(attendance_service.haversine_distance_meters(12.0, 109.0, 12.0, 109.0), 0.0, places=3)

    def test_validate_checkin_window_rejects_late(self):
        session = ClassSession(
            subject="MVP Subject",
            class_name="MVP101-64CNTT-2026",
            session_date=date(2026, 6, 10),
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        with self.assertRaises(Exception) as ctx:
            attendance_service.validate_checkin_window(session, datetime(2026, 6, 10, 7, 16))
        self.assertEqual(ctx.exception.detail["status"], "attendance_closed")
        self.assertEqual(
            ctx.exception.detail["message"],
            "Đã quá thời gian điểm danh. Hệ thống chỉ cho phép điểm danh trong 15 phút đầu buổi học.",
        )

    def test_enrollment_and_report_use_section_membership(self):
        classroom, subject, section = self.add_section_bundle()
        student = self.add_student()
        section_id = section["id"]
        enrollment = create_enrollment(
            EnrollmentCreate(course_section_id=section_id, student_id=student.id, status="active"),
            _current_user=None,
            db=self.db,
        )
        session = create_session_from_section(
            SessionFromSectionCreate(
                section_id=section_id,
                classroom_id=classroom.id,
                session_date=date(2026, 6, 10),
                start_time=time(7, 0),
                end_time=time(9, 0),
                note="Buổi học MVP",
            ),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(enrollment["student_id"], student.id)
        self.assertEqual(session.section_id, section_id)
        students = get_course_section_students(section_id, _current_user=None, db=self.db)
        self.assertEqual([item["student_code"] for item in students], ["64100001"])

        self.db.add(Attendance(student_id=student.id, session_id=session.id, status="present"))
        self.db.commit()
        _session, rows = report_service.build_session_report(session.id, self.db)
        self.assertEqual(rows[0]["status"], "present")
        self.assertEqual(rows[0]["student_code"], "64100001")

        student_enrollments = get_student_enrollments(student.id, _current_user=None, db=self.db)
        self.assertEqual(len(student_enrollments), 1)
        self.assertEqual(student_enrollments[0]["course_section_id"], section_id)

        delete_enrollment(enrollment["id"], _current_user=None, db=self.db)
        self.assertEqual(get_student_enrollments(student.id, _current_user=None, db=self.db), [])

    def test_active_sessions_returns_enrolled_section_and_status(self):
        classroom, _subject, section = self.add_section_bundle()
        student = self.add_student()
        section_id = section["id"]
        create_enrollment(
            EnrollmentCreate(course_section_id=section_id, student_id=student.id, status="active"),
            _current_user=None,
            db=self.db,
        )
        session = create_session_from_section(
            SessionFromSectionCreate(
                section_id=section_id,
                classroom_id=classroom.id,
                session_date=date(2026, 6, 10),
                start_time=time(7, 0),
                end_time=time(9, 0),
            ),
            _current_user=None,
            db=self.db,
        )

        students_module = __import__("routes.students", fromlist=["now_in_app_timezone"])
        original_now = students_module.now_in_app_timezone
        students_module.now_in_app_timezone = lambda: datetime(2026, 6, 10, 7, 5)
        try:
            items = get_my_active_sessions(student.id, db=self.db)
        finally:
            students_module.now_in_app_timezone = original_now

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["session_id"], session.id)
        self.assertEqual(items[0]["status"], "open_for_attendance")
        self.assertEqual(items[0]["attendance_deadline"], "07:15")
        self.assertEqual(items[0]["classroom_id"], classroom.id)

    def test_mobile_session_status_boundaries(self):
        session = ClassSession(
            session_date=date(2026, 6, 10),
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        self.assertEqual(_mobile_session_status(session, datetime(2026, 6, 10, 6, 59))[0], "not_started")
        self.assertEqual(_mobile_session_status(session, datetime(2026, 6, 10, 7, 15))[0], "open_for_attendance")
        self.assertEqual(_mobile_session_status(session, datetime(2026, 6, 10, 7, 16))[0], "closed")

    def test_checkin_response_contract_for_mobile_frontend(self):
        classroom, _subject, section = self.add_section_bundle()
        student = self.add_student()
        section_id = section["id"]
        create_enrollment(
            EnrollmentCreate(course_section_id=section_id, student_id=student.id, status="active"),
            _current_user=None,
            db=self.db,
        )
        session = create_session_from_section(
            SessionFromSectionCreate(
                section_id=section_id,
                classroom_id=classroom.id,
                session_date=date(2026, 6, 10),
                start_time=time(7, 0),
                end_time=time(9, 0),
            ),
            _current_user=None,
            db=self.db,
        )
        original_now = attendance_service.now_in_app_timezone
        attendance_service.now_in_app_timezone = lambda: datetime(2026, 6, 10, 7, 5)
        try:
            response = _checkin_response(
                self.db,
                AttendanceCheckIn(
                    student_code=student.student_code,
                    session_id=session.id,
                    confidence=0.86,
                    gps_lat=classroom.gps_lat,
                    gps_lng=classroom.gps_lng,
                    gps_accuracy=5,
                ),
            )
        finally:
            attendance_service.now_in_app_timezone = original_now

        self.assertEqual(response["status"], "success")
        self.assertEqual(response["message"], "Điểm danh thành công.")
        self.assertEqual(response["student_code"], student.student_code)
        self.assertEqual(response["confidence"], 0.86)
        self.assertEqual(response["distance_meters"], 0.0)
        self.assertEqual(response["allowed_radius_meters"], classroom.radius_meters)
        self.assertIsNotNone(response["check_in_time"])

    def test_checkin_error_contract_is_top_level_json(self):
        classroom, _subject, section = self.add_section_bundle()
        student = self.add_student()
        section_id = section["id"]
        create_enrollment(
            EnrollmentCreate(course_section_id=section_id, student_id=student.id, status="active"),
            _current_user=None,
            db=self.db,
        )
        session = create_session_from_section(
            SessionFromSectionCreate(
                section_id=section_id,
                classroom_id=classroom.id,
                session_date=date(2026, 6, 10),
                start_time=time(7, 0),
                end_time=time(9, 0),
            ),
            _current_user=None,
            db=self.db,
        )
        original_now = attendance_service.now_in_app_timezone
        attendance_service.now_in_app_timezone = lambda: datetime(2026, 6, 10, 7, 5)
        try:
            response = _checkin_response(
                self.db,
                AttendanceCheckIn(
                    student_code=student.student_code,
                    session_id=session.id,
                    gps_lat=13.0,
                    gps_lng=109.0,
                ),
            )
        finally:
            attendance_service.now_in_app_timezone = original_now

        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 403)
        self.assertEqual(payload["status"], "gps_out_of_range")
        self.assertEqual(payload["message"], "Bạn đang ở ngoài phạm vi điểm danh của phòng học.")
        self.assertIn("distance_meters", payload)
        self.assertEqual(payload["allowed_radius_meters"], classroom.radius_meters)


if __name__ == "__main__":
    unittest.main()
