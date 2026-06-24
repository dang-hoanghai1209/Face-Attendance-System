import os
import unittest


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_with_enough_length_for_jwt")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.audit_log import AuditLog
from models.student import Student
from models.user import User
from services.auth_service import hash_password


class AuthAPIRouteTests(unittest.TestCase):
    def setUp(self):
        self.test_engine = create_engine(
            "sqlite:///./test_auth_api.sqlite",
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

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)
        self.test_engine.dispose()
        try:
            os.remove("test_auth_api.sqlite")
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

    def add_student_profile(self, code):
        student = Student(
            student_code=code,
            full_name="Student User",
            class_name="64CNTT",
            face_status="registered",
            data_source="real",
            is_demo=False,
        )
        self.db.add(student)
        self.db.commit()
        self.db.refresh(student)
        return student

    def login_headers(self, username):
        response = self.client.post("/auth/login", json={"username": username, "password": "password123"})
        self.assertEqual(response.status_code, 200)
        return {"Authorization": f"Bearer {response.json()['access_token']}"}

    def test_login_success_and_me_with_token(self):
        self.add_user("admin", "admin")

        login_response = self.client.post("/auth/login", json={"username": "admin", "password": "password123"})
        self.assertEqual(login_response.status_code, 200)
        token = login_response.json()["access_token"]

        me_response = self.client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
        self.assertEqual(me_response.status_code, 200)
        self.assertEqual(me_response.json()["username"], "admin")
        self.assertEqual(me_response.json()["role"], "admin")

    def test_me_without_token_and_invalid_token_return_401(self):
        self.assertEqual(self.client.get("/auth/me").status_code, 401)
        response = self.client.get("/auth/me", headers={"Authorization": "Bearer invalid.token.value"})
        self.assertEqual(response.status_code, 401)

    def test_audit_logs_admin_allowed_teacher_student_forbidden(self):
        self.add_user("admin", "admin")
        self.add_user("teacher", "teacher")
        self.add_student_profile("64100001")
        self.add_user("64100001", "student")
        self.db.add(AuditLog(action="login_success", actor_username="admin", actor_role="admin"))
        self.db.commit()

        admin_response = self.client.get("/auth/audit-logs", headers=self.login_headers("admin"))
        self.assertEqual(admin_response.status_code, 200)
        self.assertEqual(admin_response.json()[0]["action"], "login_success")

        teacher_response = self.client.get("/auth/audit-logs", headers=self.login_headers("teacher"))
        self.assertEqual(teacher_response.status_code, 403)

        student_response = self.client.get("/auth/audit-logs", headers=self.login_headers("64100001"))
        self.assertEqual(student_response.status_code, 403)

    def test_private_routes_without_token_return_401(self):
        private_routes = [
            "/students/",
            "/sessions/",
            "/attendance/session/1",
            "/reports/dashboard/stats",
            "/auth/users",
            "/auth/audit-logs",
        ]

        for route in private_routes:
            with self.subTest(route=route):
                self.assertEqual(self.client.get(route).status_code, 401)

    def test_wrong_role_for_users_returns_403(self):
        self.add_user("teacher", "teacher")
        response = self.client.get("/auth/users", headers=self.login_headers("teacher"))
        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
