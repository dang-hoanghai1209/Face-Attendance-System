import os
import unittest
from datetime import date


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database import Base, SessionLocal, engine
from migrate_mis_to_lfw import migrate_mis_sessions_to_lfw
from models.session import Session as ClassSession
from models.student import Student
from services.class_service import (
    VALID_CLASS_SET,
    migrate_mis_students_to_lfw,
    student_code_matches_class,
)


class ClassServiceTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def add_student(self, student_code, class_name):
        student = Student(
            student_code=student_code,
            full_name=f"Student {student_code}",
            class_name=class_name,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def test_new_cntt_classes_are_valid(self):
        self.assertIn("63CNTT", VALID_CLASS_SET)
        self.assertIn("64CNTT", VALID_CLASS_SET)
        self.assertTrue(student_code_matches_class("63123456", "63CNTT"))
        self.assertTrue(student_code_matches_class("64123456", "64CNTT"))

    def test_migrate_mis_63_student_to_63lfw(self):
        student = self.add_student("63123456", "MIS")

        result = migrate_mis_students_to_lfw(self.db, dry_run=False)
        self.db.refresh(student)

        self.assertEqual(result["migrated_count"], 1)
        self.assertEqual(student.class_name, "63LFW")

    def test_migrate_mis_64_student_to_64lfw(self):
        student = self.add_student("64123456", "MIS")

        result = migrate_mis_students_to_lfw(self.db, dry_run=False)
        self.db.refresh(student)

        self.assertEqual(result["migrated_count"], 1)
        self.assertEqual(student.class_name, "64LFW")

    def test_migrate_mis_student_with_unknown_prefix_is_skipped(self):
        student = self.add_student("99123456", "MIS")

        result = migrate_mis_students_to_lfw(self.db, dry_run=False)
        self.db.refresh(student)

        self.assertEqual(result["migrated_count"], 0)
        self.assertEqual(result["skipped_count"], 1)
        self.assertEqual(student.class_name, "MIS")
        self.assertEqual(result["skipped"][0]["student_code"], "99123456")

    def test_migrate_mis_session_splits_to_lfw_classes(self):
        session = ClassSession(
            subject="Database",
            class_name="MIS",
            session_date=date(2026, 6, 1),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)

        result = migrate_mis_sessions_to_lfw(self.db, dry_run=False)
        self.db.refresh(session)
        class_names = {
            row.class_name
            for row in self.db.query(ClassSession).order_by(ClassSession.class_name).all()
        }

        self.assertEqual(result["migrated_count"], 1)
        self.assertEqual(result["created_count"], 1)
        self.assertEqual(session.class_name, "63LFW")
        self.assertEqual(class_names, {"63LFW", "64LFW"})


if __name__ == "__main__":
    unittest.main()
