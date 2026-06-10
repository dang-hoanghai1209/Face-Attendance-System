from datetime import date, time

from database import Base, SessionLocal, engine
from models.classroom import Classroom
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.session import Session as ClassSession
from models.student import Student
from models.subject import Subject
from models.user import User  # noqa: F401
from schema_sync import sync_schema


def get_or_create(db, model, defaults=None, **filters):
    row = db.query(model).filter_by(**filters).first()
    if row:
        return row
    row = model(**filters, **(defaults or {}))
    db.add(row)
    db.commit()
    db.refresh(row)
    return row


def main():
    Base.metadata.create_all(bind=engine)
    sync_schema(engine)
    db = SessionLocal()
    try:
        classroom = get_or_create(
            db,
            Classroom,
            name="Phòng MVP 101",
            defaults={
                "building": "Khu A",
                "gps_lat": 12.238912,
                "gps_lng": 109.196748,
                "radius_meters": 20,
                "is_active": True,
            },
        )
        subject = get_or_create(
            db,
            Subject,
            subject_code="MVP101",
            defaults={
                "subject_name": "Học phần kiểm thử MVP",
                "credits": 3,
                "department": "Công nghệ thông tin",
            },
        )
        section = get_or_create(
            db,
            CourseSection,
            section_code="MVP101-64CNTT-2026",
            defaults={
                "subject_id": subject.id,
                "semester": "2026-1",
                "academic_year": "2025-2026",
                "lecturer_name": "Giảng viên MVP",
                "status": "open",
            },
        )
        students = [
            get_or_create(
                db,
                Student,
                student_code=code,
                defaults={
                    "full_name": name,
                    "class_name": "64CNTT",
                    "face_status": "registered",
                    "data_source": "real",
                    "is_demo": False,
                    "registration_method": "camera",
                },
            )
            for code, name in [
                ("64100001", "Sinh viên MVP 1"),
                ("64100002", "Sinh viên MVP 2"),
                ("64100003", "Sinh viên MVP 3"),
            ]
        ]
        for student in students:
            get_or_create(
                db,
                Enrollment,
                course_section_id=section.id,
                student_id=student.id,
                defaults={"status": "active"},
            )

        session = (
            db.query(ClassSession)
            .filter(
                ClassSession.section_id == section.id,
                ClassSession.classroom_id == classroom.id,
                ClassSession.session_date == date.today(),
            )
            .first()
        )
        if not session:
            session = ClassSession(
                subject=subject.subject_name,
                class_name=section.section_code,
                section_id=section.id,
                classroom_id=classroom.id,
                session_date=date.today(),
                start_time=time(7, 0),
                end_time=time(9, 0),
                note="Buổi học seed MVP 1",
                created_by=section.lecturer_name,
            )
            db.add(session)
            db.commit()
            db.refresh(session)

        print("Seed MVP 1 created:")
        print(f"- classroom_id={classroom.id}")
        print(f"- subject_id={subject.id}")
        print(f"- section_id={section.id}")
        print(f"- session_id={session.id}")
        print("- student_codes=64100001, 64100002, 64100003")
    finally:
        db.close()


if __name__ == "__main__":
    main()
