import os
import unittest


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_with_enough_length_for_jwt")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

from fastapi import HTTPException

from database import Base, SessionLocal, engine
from models.audit_log import AuditLog
from models.student import Student
from models.user import User
from routes import attendance as attendance_routes
from routes.auth import UserCreateRequest, UserUpdateRequest, create_user, update_user
from routes.auth import LoginRequest, login
from services.auth_service import (
    create_access_token,
    decode_access_token,
    hash_password,
    require_role,
)


class AuthRBACTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

    def add_student(self, code="64100001"):
        student = Student(
            student_code=code,
            full_name=f"Student {code}",
            class_name="64CNTT",
            face_status="registered",
            data_source="real",
            is_demo=False,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def add_user(self, username="admin", role="admin"):
        user = User(
            username=username,
            password_hash=hash_password("password123"),
            full_name=f"User {username}",
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def test_jwt_contains_user_identity_and_role(self):
        user = self.add_user(username="teacher01", role="teacher")

        token = create_access_token(user)
        payload = decode_access_token(token)

        self.assertEqual(payload["sub"], str(user.id))
        self.assertEqual(payload["username"], "teacher01")
        self.assertEqual(payload["role"], "teacher")

    def test_legacy_roles_are_rejected(self):
        with self.assertRaises(ValueError):
            require_role("lecturer")
        with self.assertRaises(ValueError):
            require_role("viewer")

    def test_admin_can_create_and_update_user_role(self):
        admin = self.add_user()

        created = create_user(
            UserCreateRequest(
                username="teacher01",
                password="password123",
                full_name="Teacher One",
                role="teacher",
            ),
            _current_user=admin,
            db=self.db,
        )

        self.assertEqual(created["username"], "teacher01")
        self.assertEqual(created["role"], "teacher")

        updated = update_user(
            created["id"],
            UserUpdateRequest(role="student", is_active=False),
            _current_user=admin,
            db=self.db,
        )

        self.assertEqual(updated["role"], "student")
        self.assertFalse(updated["is_active"])
        actions = [row.action for row in self.db.query(AuditLog).order_by(AuditLog.id.asc()).all()]
        self.assertEqual(actions, ["user_created", "user_updated"])

    def test_login_writes_success_and_failure_audit_logs(self):
        self.add_user(username="teacher01", role="teacher")

        response = login(LoginRequest(username="teacher01", password="password123"), db=self.db)
        self.assertEqual(response["user"]["username"], "teacher01")
        with self.assertRaises(HTTPException):
            login(LoginRequest(username="teacher01", password="wrong-password"), db=self.db)

        actions = [row.action for row in self.db.query(AuditLog).order_by(AuditLog.id.asc()).all()]
        self.assertEqual(actions, ["login_success", "login_failed"])

    def test_create_user_rejects_invalid_role(self):
        admin = self.add_user()

        with self.assertRaises(HTTPException) as context:
            create_user(
                UserCreateRequest(username="legacy", password="password123", role="viewer"),
                _current_user=admin,
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 400)

    def test_student_cannot_checkin_for_another_student(self):
        self.add_student("64100001")
        self.add_student("64100002")
        user = self.add_user(username="64100001", role="student")

        with self.assertRaises(HTTPException) as context:
            attendance_routes.record_checkin(
                attendance_routes.AttendanceCheckIn(student_code="64100002", session_id=1),
                current_user=user,
                db=self.db,
            )

        self.assertEqual(context.exception.status_code, 403)

    def test_student_can_checkin_for_self_and_teacher_can_checkin_for_any_student(self):
        self.add_student("64100001")
        self.add_student("64100002")
        student_user = self.add_user(username="64100001", role="student")
        teacher_user = self.add_user(username="teacher01", role="teacher")
        original_checkin_response = attendance_routes._checkin_response
        attendance_routes._checkin_response = lambda _db, data: {
            "student_code": data.student_code,
            "session_id": data.session_id,
        }
        try:
            own_response = attendance_routes.record_checkin(
                attendance_routes.AttendanceCheckIn(student_code="64100001", session_id=10),
                current_user=student_user,
                db=self.db,
            )
            teacher_response = attendance_routes.record_checkin(
                attendance_routes.AttendanceCheckIn(student_code="64100002", session_id=11),
                current_user=teacher_user,
                db=self.db,
            )
        finally:
            attendance_routes._checkin_response = original_checkin_response

        self.assertEqual(own_response["student_code"], "64100001")
        self.assertEqual(teacher_response["student_code"], "64100002")


if __name__ == "__main__":
    unittest.main()
