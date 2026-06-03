import argparse
import json

from dotenv import load_dotenv
from sqlalchemy import func

from database import SessionLocal
from models.attendance import Attendance
from models.session import Session as ClassSession
from models.student import Student
from services.class_service import LEGACY_MIS_CLASS, migrate_mis_students_to_lfw


def collect_mis_session_warnings(db):
    warnings = []
    sessions = (
        db.query(ClassSession)
        .filter(ClassSession.class_name == LEGACY_MIS_CLASS)
        .order_by(ClassSession.id.asc())
        .all()
    )
    for session in sessions:
        attendance_by_prefix = (
            db.query(
                func.substring(Student.student_code, 1, 2).label("prefix"),
                func.count(Attendance.id).label("count"),
            )
            .join(Attendance, Attendance.student_id == Student.id)
            .filter(Attendance.session_id == session.id)
            .group_by("prefix")
            .order_by("prefix")
            .all()
        )
        warnings.append(
            {
                "session_id": session.id,
                "subject": session.subject,
                "session_date": session.session_date.isoformat() if session.session_date else None,
                "attendance_by_prefix": [
                    {"prefix": row.prefix, "count": row.count} for row in attendance_by_prefix
                ],
                "message": (
                    "Session still uses legacy MIS class. Review manually and update to 63LFW/64LFW "
                    "or split into separate sessions if needed."
                ),
            }
        )
    return warnings


def _session_duplicate_exists(db, session, class_name):
    return (
        db.query(ClassSession)
        .filter(
            ClassSession.id != session.id,
            ClassSession.subject == session.subject,
            ClassSession.class_name == class_name,
            ClassSession.session_date == session.session_date,
            ClassSession.start_time == session.start_time,
            ClassSession.end_time == session.end_time,
        )
        .first()
        is not None
    )


def migrate_mis_sessions_to_lfw(db, dry_run=True):
    sessions = (
        db.query(ClassSession)
        .filter(ClassSession.class_name == LEGACY_MIS_CLASS)
        .order_by(ClassSession.id.asc())
        .all()
    )
    migrated = []
    created = []

    for session in sessions:
        migrated.append(
            {
                "session_id": session.id,
                "from_class": session.class_name,
                "to_class": "63LFW",
            }
        )
        if not dry_run:
            session.class_name = "63LFW"

        if not _session_duplicate_exists(db, session, "64LFW"):
            created.append(
                {
                    "source_session_id": session.id,
                    "class_name": "64LFW",
                    "subject": session.subject,
                    "session_date": session.session_date.isoformat() if session.session_date else None,
                }
            )
            if not dry_run:
                db.add(
                    ClassSession(
                        subject=session.subject,
                        class_name="64LFW",
                        session_date=session.session_date,
                        start_time=session.start_time,
                        end_time=session.end_time,
                        created_by=session.created_by,
                    )
                )

    if not dry_run:
        db.commit()

    return {
        "dry_run": dry_run,
        "migrated_count": len(migrated),
        "created_count": len(created),
        "migrated": migrated,
        "created": created,
    }


def main():
    parser = argparse.ArgumentParser(description="Migrate legacy MIS students to 63LFW/64LFW.")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply changes. Without this flag the script only prints a dry-run report.",
    )
    args = parser.parse_args()

    load_dotenv()
    db = SessionLocal()
    try:
        result = migrate_mis_students_to_lfw(db, dry_run=not args.apply)
        result["sessions"] = migrate_mis_sessions_to_lfw(db, dry_run=not args.apply)
        result["mis_session_warnings"] = collect_mis_session_warnings(db)
        print(json.dumps(result, ensure_ascii=False, indent=2))
    finally:
        db.close()


if __name__ == "__main__":
    main()
