import os
import unittest
from datetime import date, time


os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

from fastapi import HTTPException
from pydantic import ValidationError

from database import Base, SessionLocal, engine
from models.session import Session as ClassSession
from routes.sessions import SessionCreate, SessionUpdate, create_session, update_session


class SessionRouteTests(unittest.TestCase):
    def setUp(self):
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = SessionLocal()

    def tearDown(self):
        self.db.close()
        Base.metadata.drop_all(bind=engine)

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
        session = create_session(
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

        self.assertEqual(session.start_time, time(7, 0))
        self.assertEqual(session.end_time, time(9, 0))

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


if __name__ == "__main__":
    unittest.main()
