import os
import unittest
from datetime import date


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi import HTTPException

from database import Base, SessionLocal, engine
from models.enrollment import Enrollment
from models.session import Session as ClassSession
from models.student import Student
from routes.enrollments import (
    SessionEnrollmentImportRequest,
    SessionEnrollmentRequest,
    delete_session_enrollment,
    enroll_students_in_session,
    get_session_enrollments,
    import_session_enrollments_by_class,
)


class SessionEnrollmentRouteTests(unittest.TestCase):
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

    def add_student(self, code, class_name="63LFW", full_name=None):
        student = Student(
            student_code=code,
            full_name=full_name or f"Student {code}",
            class_name=class_name,
            data_source="real",
            is_demo=False,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def test_enroll_multiple_student_codes_reports_added_and_failed(self):
        session = self.add_session()
        first = self.add_student("63100001")
        second = self.add_student("63100002")

        response = enroll_students_in_session(
            session.id,
            SessionEnrollmentRequest(student_codes=[first.student_code, second.student_code, "missing"]),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(response["added"], 2)
        self.assertEqual(response["skipped"], 0)
        self.assertEqual(response["failed"], 1)
        self.assertEqual(response["failed_items"][0]["student_code"], "missing")
        self.assertEqual(
            [item["student_code"] for item in response["enrolled"]],
            ["63100001", "63100002"],
        )

    def test_duplicate_session_enrollment_is_skipped(self):
        session = self.add_session()
        student = self.add_student("63100001")
        self.db.add(Enrollment(session_id=session.id, student_id=student.id))
        self.db.commit()

        response = enroll_students_in_session(
            session.id,
            SessionEnrollmentRequest(student_codes=[student.student_code]),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(response["added"], 0)
        self.assertEqual(response["skipped"], 1)
        self.assertEqual(response["skipped_student_codes"], [student.student_code])
        self.assertEqual(
            self.db.query(Enrollment).filter(Enrollment.session_id == session.id, Enrollment.student_id == student.id).count(),
            1,
        )

    def test_list_session_enrollments_returns_student_fields(self):
        session = self.add_session()
        student = self.add_student("63100001", full_name="Nguyen Van A")
        self.db.add(Enrollment(session_id=session.id, student_id=student.id, note="official"))
        self.db.commit()

        response = get_session_enrollments(session.id, _current_user=None, db=self.db)

        self.assertEqual(len(response), 1)
        self.assertEqual(response[0]["student_code"], student.student_code)
        self.assertEqual(response[0]["full_name"], "Nguyen Van A")
        self.assertEqual(response[0]["class_name"], "63LFW")
        self.assertEqual(response[0]["note"], "official")

    def test_delete_session_enrollment_removes_student(self):
        session = self.add_session()
        student = self.add_student("63100001")
        self.db.add(Enrollment(session_id=session.id, student_id=student.id))
        self.db.commit()

        response = delete_session_enrollment(session.id, student.student_code, _current_user=None, db=self.db)

        self.assertEqual(response["student_code"], student.student_code)
        self.assertEqual(self.db.query(Enrollment).filter(Enrollment.session_id == session.id).count(), 0)

        with self.assertRaises(HTTPException) as ctx:
            delete_session_enrollment(session.id, student.student_code, _current_user=None, db=self.db)
        self.assertEqual(ctx.exception.status_code, 404)

    def test_import_session_enrollments_by_class(self):
        session = self.add_session()
        first = self.add_student("63100001", class_name="63LFW")
        second = self.add_student("63100002", class_name="63LFW")
        self.add_student("64100001", class_name="64LFW")
        self.db.add(Enrollment(session_id=session.id, student_id=first.id))
        self.db.commit()

        response = import_session_enrollments_by_class(
            session.id,
            SessionEnrollmentImportRequest(class_name="63LFW"),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(response["total_found"], 2)
        self.assertEqual(response["added"], 1)
        self.assertEqual(response["skipped"], 1)
        self.assertEqual(response["skipped_student_codes"], [first.student_code])
        self.assertEqual(
            sorted(item["student_code"] for item in response["enrolled"]),
            [first.student_code, second.student_code],
        )


if __name__ == "__main__":
    unittest.main()
