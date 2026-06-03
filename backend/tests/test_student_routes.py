import os
import unittest


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from database import Base, SessionLocal, engine
from routes.students import StudentBase, create_student


class StudentRouteTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def test_create_student_accepts_63cntt(self):
        student = create_student(
            StudentBase(
                student_code="63123456",
                full_name="Student 63 CNTT",
                class_name="63CNTT",
            ),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(student.class_name, "63CNTT")

    def test_create_student_accepts_64cntt(self):
        student = create_student(
            StudentBase(
                student_code="64123456",
                full_name="Student 64 CNTT",
                class_name="64CNTT",
            ),
            _current_user=None,
            db=self.db,
        )

        self.assertEqual(student.class_name, "64CNTT")


if __name__ == "__main__":
    unittest.main()
