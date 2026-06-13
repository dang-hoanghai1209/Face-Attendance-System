import os
import unittest
from datetime import date, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi import HTTPException
from pydantic import ValidationError

from database import Base, SessionLocal, engine
from models.attendance import Attendance
from models.attendance_scan import AttendanceScan
from models.session import Session as ClassSession
from models.student import Student
from routes.sessions import SessionCreate, SessionUpdate, create_session, delete_session, update_session


class SessionRouteTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def add_students(self, class_name="63LFW", count=5):
        for index in range(count):
            self.db.add(
                Student(
                    student_code=f"6313{index:04d}",
                    full_name=f"Student {index + 1}",
                    class_name=class_name,
                    face_status="registered",
                    data_source="real",
                    is_demo=False,
                )
            )
        self.db.commit()

    def test_create_session_requires_valid_time_range(self):
        with self.assertRaises(ValidationError):
            SessionCreate(
                subject="Database",
                class_name="63LFW",
                session_date=date(2026, 6, 1),
                start_time=time(9, 0),
                end_time=time(9, 0),
            )

    def test_create_session_saves_start_and_end_time(self):
        self.add_students()

        session = create_session(
            SessionCreate(
                subject="Database",
                class_name="63LFW",
                latitude=12.238912,
                longitude=109.196748,
                session_date=date(2026, 6, 1),
                start_time=time(7, 0),
                end_time=time(9, 0),
            ),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(session.start_time, time(7, 0))
        self.assertEqual(session.end_time, time(9, 0))

    def test_create_session_requires_gps_coordinates(self):
        self.add_students()

        with self.assertRaises(HTTPException) as context:
            create_session(
                SessionCreate(
                    subject="Database",
                    class_name="63LFW",
                    session_date=date(2026, 6, 1),
                    start_time=time(7, 0),
                    end_time=time(9, 0),
                ),
                _current_user=None,
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(context.exception.detail, "Thiếu tọa độ GPS của buổi học")

    def test_create_session_requires_minimum_five_students(self):
        self.add_students(count=4)

        with self.assertRaises(HTTPException) as context:
            create_session(
                SessionCreate(
                    subject="Database",
                    class_name="63LFW",
                    latitude=12.238912,
                    longitude=109.196748,
                    session_date=date(2026, 6, 1),
                    start_time=time(7, 0),
                    end_time=time(9, 0),
                ),
                _current_user=None,
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 422)
        self.assertEqual(context.exception.detail, "Lớp cần tối thiểu 5 sinh viên")

    def test_update_session_rejects_invalid_effective_time_range(self):
        session = ClassSession(
            subject="Database",
            class_name="63LFW",
            session_date=date(2026, 6, 1),
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        with self.assertRaises(HTTPException):
            update_session(
                session.id,
                SessionUpdate(end_time=time(6, 59)),
                _current_user=None,
                db=self.db,
            )

    def test_delete_session_removes_attendance_scans(self):
        student = Student(
            student_code="63130001",
            full_name="Student 1",
            class_name="63LFW",
            face_status="registered",
            data_source="real",
            is_demo=False,
        )
        session = ClassSession(
            subject="Database",
            class_name="63LFW",
            latitude=12.238912,
            longitude=109.196748,
            session_date=date(2026, 6, 1),
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        self.db.add_all([student, session])
        self.db.commit()
        self.db.refresh(student)
        self.db.refresh(session)

        attendance = Attendance(student_id=student.id, session_id=session.id, status="present")
        self.db.add(attendance)
        self.db.commit()
        self.db.refresh(attendance)
        self.db.add(AttendanceScan(attendance_id=attendance.id, scan_index=1))
        self.db.commit()
        attendance_id = attendance.id

        response = delete_session(session.id, _current_user=None, db=self.db)

        self.assertEqual(response["message"], f"Đã xóa buổi học {session.id}.")
        self.assertIsNone(self.db.query(ClassSession).filter(ClassSession.id == session.id).first())
        self.assertIsNone(self.db.query(Attendance).filter(Attendance.id == attendance_id).first())
        self.assertEqual(
            self.db.query(AttendanceScan).filter(AttendanceScan.attendance_id == attendance_id).count(),
            0,
        )


if __name__ == "__main__":
    unittest.main()
