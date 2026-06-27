import os
import unittest
from datetime import date
from pathlib import Path


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test_secret_key_with_enough_length_for_jwt")
os.environ.setdefault("JWT_EXPIRE_MINUTES", "60")

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from database import Base, get_db
from main import app
from models.course_section import CourseSection
from models.security_alert import SecurityAlert
from models.session import Session as ClassSession
from models.subject import Subject
from models.user import User
from routes import media_private
from services.auth_service import create_access_token, hash_password


class PrivateMediaRouteTests(unittest.TestCase):
    def setUp(self):
        self.test_engine = create_engine(
            "sqlite:///./test_media_private.sqlite",
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
        self.created_files = []
        self.test_media_dir = media_private.MEDIA_ROOT / "private-test"
        self.test_media_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        app.dependency_overrides.clear()
        self.client.close()
        self.db.close()
        Base.metadata.drop_all(bind=self.test_engine)
        self.test_engine.dispose()
        for path in self.created_files:
            if path.exists():
                path.unlink()
        for path in sorted(self.test_media_dir.glob("**/*"), reverse=True):
            if path.is_file():
                path.unlink()
            elif path.is_dir():
                try:
                    path.rmdir()
                except OSError:
                    pass
        try:
            self.test_media_dir.rmdir()
        except OSError:
            pass
        try:
            os.remove("test_media_private.sqlite")
        except OSError:
            pass

    def add_user(self, username, role, full_name=None):
        user = User(
            username=username,
            password_hash=hash_password("password123"),
            full_name=full_name or f"{role} user",
            role=role,
            is_active=True,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def headers_for(self, user):
        return {"Authorization": f"Bearer {create_access_token(user)}"}

    def add_session(self, created_by=None, lecturer_name=None):
        section_id = None
        if lecturer_name:
            subject = Subject(subject_code=f"SUB{len(lecturer_name)}", subject_name="Security")
            self.db.add(subject)
            self.db.commit()
            self.db.refresh(subject)
            section = CourseSection(
                section_code=f"SEC-{lecturer_name}",
                class_name="63CNTT",
                subject_id=subject.id,
                lecturer_name=lecturer_name,
            )
            self.db.add(section)
            self.db.commit()
            self.db.refresh(section)
            section_id = section.id
        session = ClassSession(
            subject="Security",
            class_name="63CNTT",
            section_id=section_id,
            session_date=date(2026, 6, 1),
            created_by=created_by,
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return session

    def write_image(self, name="capture.jpg", content=b"fake-jpeg-bytes"):
        path = self.test_media_dir / name
        path.write_bytes(content)
        self.created_files.append(path)
        return f"media/private-test/{name}", content

    def add_alert(self, session, captured_img):
        alert = SecurityAlert(
            session_id=session.id,
            alert_type="UNKNOWN_FACE",
            captured_img=captured_img,
        )
        self.db.add(alert)
        self.db.commit()
        self.db.refresh(alert)
        return alert

    def test_anonymous_cannot_view_alert_image(self):
        session = self.add_session()
        captured_img, _content = self.write_image()
        alert = self.add_alert(session, captured_img)

        response = self.client.get(f"/media-private/alerts/{alert.id}/image")

        self.assertEqual(response.status_code, 401)

    def test_student_is_blocked_from_alert_image(self):
        user = self.add_user("64100001", "student")
        session = self.add_session()
        captured_img, _content = self.write_image()
        alert = self.add_alert(session, captured_img)

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 403)

    def test_teacher_without_session_scope_is_blocked(self):
        user = self.add_user("teacher01", "teacher", full_name="Teacher One")
        session = self.add_session(created_by="other_teacher")
        captured_img, _content = self.write_image()
        alert = self.add_alert(session, captured_img)

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 403)

    def test_teacher_with_created_by_scope_can_view_alert_image(self):
        user = self.add_user("teacher01", "teacher", full_name="Teacher One")
        session = self.add_session(created_by="teacher01")
        captured_img, content = self.write_image()
        alert = self.add_alert(session, captured_img)

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/jpeg")
        self.assertEqual(response.headers["cache-control"], "private, no-store")
        self.assertEqual(response.content, content)

    def test_teacher_with_lecturer_name_scope_can_view_alert_image(self):
        user = self.add_user("teacher01", "teacher", full_name="Teacher One")
        session = self.add_session(lecturer_name="Teacher One")
        captured_img, content = self.write_image()
        alert = self.add_alert(session, captured_img)

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)

    def test_admin_can_view_alert_image(self):
        user = self.add_user("admin", "admin")
        session = self.add_session()
        captured_img, content = self.write_image()
        alert = self.add_alert(session, captured_img)

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.content, content)

    def test_missing_alert_returns_404(self):
        user = self.add_user("admin", "admin")

        response = self.client.get("/media-private/alerts/999999/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 404)

    def test_alert_without_image_returns_404(self):
        user = self.add_user("admin", "admin")
        session = self.add_session()
        alert = self.add_alert(session, None)

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 404)

    def test_path_traversal_is_blocked(self):
        user = self.add_user("admin", "admin")
        session = self.add_session()
        alert = self.add_alert(session, "media/private-test/../capture.jpg")

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 403)

    def test_path_outside_allowed_media_roots_is_blocked(self):
        user = self.add_user("admin", "admin")
        session = self.add_session()
        alert = self.add_alert(session, "reports/evaluation_details.csv")

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 403)

    def test_missing_file_returns_404(self):
        user = self.add_user("admin", "admin")
        session = self.add_session()
        alert = self.add_alert(session, "media/private-test/missing.jpg")

        response = self.client.get(f"/media-private/alerts/{alert.id}/image", headers=self.headers_for(user))

        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()
