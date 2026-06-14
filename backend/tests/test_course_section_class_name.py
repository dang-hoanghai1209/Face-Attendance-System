import os
import unittest
from datetime import date, time

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("APP_TIMEZONE", "Asia/Nha_Trang")

from fastapi import HTTPException
from pydantic import ValidationError

from database import Base, SessionLocal, engine
from models.classroom import Classroom
from models.course_section import CourseSection
from models.session import Session as ClassSession
from models.subject import Subject
from routes.course_sections import CourseSectionCreate, create_course_section
from routes.sessions import SessionFromSectionCreate, create_session_from_section, SessionUpdate, update_session


class CourseSectionClassNameTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

        # Create basic classroom and subject
        self.classroom = Classroom(
            name="Room 101",
            building="Building A",
            gps_lat=12.238912,
            gps_lng=109.196748,
            radius_meters=20,
            is_active=True,
        )
        self.subject = Subject(
            subject_code="INS-631-SUB",
            subject_name="Khai phá dữ liệu",
            credits=3,
            department="CNTT",
        )
        self.db.add_all([self.classroom, self.subject])
        self.db.commit()
        self.db.refresh(self.classroom)
        self.db.refresh(self.subject)

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_create_course_section_with_class_name_succeeds(self):
        section = create_course_section(
            CourseSectionCreate(
                section_code="INS-631",
                class_name="64CNTT",
                subject_id=self.subject.id,
                semester="2026-1",
                academic_year="2025-2026",
                lecturer_name="Giảng viên A",
                status="open",
            ),
            _current_user=None,
            db=self.db,
        )
        self.assertEqual(section["section_code"], "INS-631")
        self.assertEqual(section["class_name"], "64CNTT")

        # Verify in database
        db_section = self.db.query(CourseSection).filter(CourseSection.id == section["id"]).first()
        self.assertIsNotNone(db_section)
        self.assertEqual(db_section.class_name, "64CNTT")

    def test_create_session_from_course_section_assigns_class_name_and_keeps_section_id(self):
        # Create course section
        section = create_course_section(
            CourseSectionCreate(
                section_code="INS-631",
                class_name="64CNTT",
                subject_id=self.subject.id,
                semester="2026-1",
                academic_year="2025-2026",
                lecturer_name="Giảng viên A",
                status="open",
            ),
            _current_user=None,
            db=self.db,
        )

        # Create session from section
        session = create_session_from_section(
            SessionFromSectionCreate(
                section_id=section["id"],
                classroom_id=self.classroom.id,
                session_date=date(2026, 6, 15),
                start_time=time(7, 0),
                end_time=time(9, 0),
                note="Buổi học 1",
            ),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(session.class_name, "64CNTT")
        self.assertNotEqual(session.class_name, "INS-631")  # Verify section_code is not converted to class_name
        self.assertEqual(session.section_id, section["id"])

    def test_create_session_from_section_skips_week_9_holiday(self):
        section = create_course_section(
            CourseSectionCreate(
                section_code="INS-631",
                class_name="64CNTT",
                subject_id=self.subject.id,
                semester="2026-1",
                academic_year="2025-2026",
                lecturer_name="Giảng viên A",
                status="open",
            ),
            _current_user=None,
            db=self.db,
        )

        create_session_from_section(
            SessionFromSectionCreate(
                section_id=section["id"],
                classroom_id=self.classroom.id,
                session_date=date(2026, 6, 15),
                start_time=time(7, 0),
                end_time=time(9, 0),
                weeks=15,
            ),
            _current_user=None,
            db=self.db,
        )

        sessions = (
            self.db.query(ClassSession)
            .filter(ClassSession.section_id == section["id"])
            .order_by(ClassSession.session_date.asc())
            .all()
        )

        self.assertEqual(len(sessions), 14)
        self.assertEqual(sessions[0].session_date, date(2026, 6, 15))
        self.assertEqual(sessions[7].session_date, date(2026, 8, 3))
        self.assertEqual(sessions[8].session_date, date(2026, 8, 17))
        self.assertEqual(sessions[13].session_date, date(2026, 9, 21))

    def test_create_session_from_section_with_missing_class_name_raises_400(self):
        # Create course section without class_name
        section = create_course_section(
            CourseSectionCreate(
                section_code="INS-631",
                class_name=None,
                subject_id=self.subject.id,
                semester="2026-1",
                academic_year="2025-2026",
                lecturer_name="Giảng viên A",
                status="open",
            ),
            _current_user=None,
            db=self.db,
        )

        # Try to create session and expect HTTPException 400
        with self.assertRaises(HTTPException) as context:
            create_session_from_section(
                SessionFromSectionCreate(
                    section_id=section["id"],
                    classroom_id=self.classroom.id,
                    session_date=date(2026, 6, 15),
                    start_time=time(7, 0),
                    end_time=time(9, 0),
                    note="Buổi học 1",
                ),
                _current_user=None,
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 400)
        self.assertEqual(context.exception.detail, "Lớp học phần chưa chọn mã lớp sinh viên.")

    def test_update_session_with_valid_class_name_does_not_fail(self):
        # Create a session directly
        session = ClassSession(
            subject="Khai phá dữ liệu",
            class_name="64CNTT",
            session_date=date(2026, 6, 15),
            start_time=time(7, 0),
            end_time=time(9, 0),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        # Update the session's class name, should not fail validation
        updated = update_session(
            session.id,
            SessionUpdate(class_name="63TTQL"),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(updated.class_name, "63TTQL")


if __name__ == "__main__":
    unittest.main()
