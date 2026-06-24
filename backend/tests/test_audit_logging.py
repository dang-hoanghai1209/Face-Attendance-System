import os
import unittest
from datetime import date, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_with_enough_length_for_jwt")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.attendance import Attendance
from models.audit_log import AuditLog
from models.classroom import Classroom
from models.course_section import CourseSection
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
from models.user import User
from routes.attendance import delete_attendance_record
from routes.classrooms import ClassroomCreate, ClassroomUpdate, create_classroom, update_classroom
from routes.course_sections import CourseSectionCreate, CourseSectionUpdate, create_course_section, update_course_section
from routes.students import StudentBase, StudentUpdate, create_student, update_student
from routes.subjects import SubjectCreate, SubjectUpdate, create_subject, update_subject
from services.auth_service import hash_password


class AuditLoggingTests(unittest.TestCase):
    def setUp(self):
        self.test_engine = create_engine(
            "sqlite:///./test_audit_logging.sqlite",
            connect_args={"check_same_thread": False},
        )
        self.TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.test_engine)
        Base.metadata.drop_all(bind=self.test_engine)
        Base.metadata.create_all(bind=self.test_engine)
        self.db = self.TestSessionLocal()

        def override_db():
            db = self.TestSessionLocal()
            try:
                yield db
            finally:
                db.close()

        app.dependency_overrides[get_db] = override_db
        self.client = TestClient(app)
        self.admin = self.add_user("admin", "admin")

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)
        self.test_engine.dispose()
        try:
            os.remove("test_audit_logging.sqlite")
        except OSError:
            pass

    def add_user(self, username, role):
        user = User(
            username=username,
            password_hash=hash_password("password123"),
            full_name=f"{role} user",
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def latest_log(self, action):
        return (
            self.db.query(AuditLog)
            .filter(AuditLog.action == action)
            .order_by(AuditLog.id.desc())
            .first()
        )

    def test_login_success_and_failure_write_audit_metadata(self):
        failed = self.client.post(
            "/auth/login",
            json={"username": "admin", "password": "wrong-password"},
            headers={"user-agent": "audit-test-agent"},
        )
        self.assertEqual(failed.status_code, 401)

        success = self.client.post(
            "/auth/login",
            json={"username": "admin", "password": "password123"},
            headers={"user-agent": "audit-test-agent"},
        )
        self.assertEqual(success.status_code, 200)

        failed_log = self.latest_log("login_failed")
        success_log = self.latest_log("login_success")
        self.assertEqual(failed_log.actor_username, "admin")
        self.assertEqual(success_log.actor_user_id, self.admin.id)
        self.assertEqual(success_log.actor_role, "admin")
        self.assertEqual(success_log.details["user_agent"], "audit-test-agent")
        self.assertIn("ip_address", success_log.details)

    def test_student_create_and_update_write_old_new_values(self):
        student = create_student(
            StudentBase(student_code="63123456", full_name="Student One", class_name="63CNTT"),
            _current_user=self.admin,
            db=self.db,
        )
        created_log = self.latest_log("student_created")
        self.assertEqual(created_log.actor_user_id, self.admin.id)
        self.assertEqual(created_log.details["new_value"]["student_code"], "63123456")

        update_student(
            student.id,
            StudentUpdate(full_name="Student Renamed"),
            _current_user=self.admin,
            db=self.db,
        )
        updated_log = self.latest_log("student_updated")
        self.assertEqual(updated_log.details["old_value"]["full_name"], "Student One")
        self.assertEqual(updated_log.details["new_value"]["full_name"], "Student Renamed")
        self.assertEqual(updated_log.details["changed_fields"], ["full_name"])

    def test_attendance_delete_writes_old_value(self):
        student = Student(
            student_code="63123457",
            full_name="Student Two",
            class_name="63CNTT",
            face_status="registered",
            data_source="real",
            is_demo=False,
        )
        session = ClassSession(
            subject="Security",
            class_name="63CNTT",
            session_date=date(2026, 6, 1),
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        self.db.add_all([student, session])
        self.db.commit()
        self.db.refresh(student)
        self.db.refresh(session)
        record = Attendance(student_id=student.id, session_id=session.id, status="present")
        self.db.add(record)
        self.db.commit()
        self.db.refresh(record)

        delete_attendance_record(record.id, current_user=self.admin, db=self.db)

        deleted_log = self.latest_log("attendance_deleted")
        self.assertEqual(deleted_log.target_id, str(record.id))
        self.assertEqual(deleted_log.details["old_value"]["student_id"], student.id)
        self.assertEqual(deleted_log.details["old_value"]["status"], "present")

    def test_academic_crud_routes_write_audit_logs(self):
        classroom = create_classroom(
            ClassroomCreate(name="A101", building="A", gps_lat=12.0, gps_lng=109.0, radius_meters=50),
            _current_user=self.admin,
            db=self.db,
        )
        update_classroom(
            classroom.id,
            ClassroomUpdate(radius_meters=60),
            _current_user=self.admin,
            db=self.db,
        )

        subject = create_subject(
            SubjectCreate(subject_code="SEC101", subject_name="Security", credits=3),
            _current_user=self.admin,
            db=self.db,
        )
        update_subject(
            subject.id,
            SubjectUpdate(subject_name="Backend Security"),
            _current_user=self.admin,
            db=self.db,
        )

        section = create_course_section(
            CourseSectionCreate(subject_id=subject.id, section_code="SEC101-01", class_name="63CNTT"),
            _current_user=self.admin,
            db=self.db,
        )
        update_course_section(
            section["id"],
            CourseSectionUpdate(status="closed"),
            _current_user=self.admin,
            db=self.db,
        )

        self.assertIsNotNone(self.latest_log("classroom_created"))
        self.assertEqual(self.latest_log("classroom_updated").details["old_value"]["radius_meters"], 50)
        self.assertIsNotNone(self.latest_log("subject_created"))
        self.assertEqual(self.latest_log("subject_updated").details["new_value"]["subject_name"], "Backend Security")
        self.assertIsNotNone(self.latest_log("course_section_created"))
        self.assertEqual(self.latest_log("course_section_updated").details["new_value"]["status"], "closed")


if __name__ == "__main__":
    unittest.main()
