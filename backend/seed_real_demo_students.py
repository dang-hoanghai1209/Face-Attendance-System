from dotenv import load_dotenv
from sqlalchemy import func

from database import SessionLocal
from models.session import Session as ClassSession
from models.student import Student


load_dotenv()

DEFAULT_CLASS_NAME = "63LFW"
STUDENTS = [
    ("63000001", "Demo Student 01"),
    ("63000002", "Demo Student 02"),
    ("63000003", "Demo Student 03"),
    ("63000004", "Demo Student 04"),
    ("63000005", "Demo Student 05"),
    ("64000006", "Demo Student 06"),
    ("64000007", "Demo Student 07"),
    ("64000008", "Demo Student 08"),
    ("64000009", "Demo Student 09"),
    ("64000010", "Demo Student 10"),
]


def first_class_name(db):
    class_name = (
        db.query(Student.class_name)
        .filter(Student.class_name.isnot(None), Student.class_name != "")
        .order_by(Student.class_name.asc())
        .limit(1)
        .scalar()
    )
    if class_name:
        return class_name

    return (
        db.query(ClassSession.class_name)
        .filter(ClassSession.class_name.isnot(None), ClassSession.class_name != "")
        .order_by(ClassSession.class_name.asc())
        .limit(1)
        .scalar()
    ) or DEFAULT_CLASS_NAME


def seed_real_demo_students():
    db = SessionLocal()
    inserted = 0
    skipped = 0

    try:
        class_name = first_class_name(db)
        for student_code, full_name in STUDENTS:
            existing = db.query(Student).filter(Student.student_code == student_code).first()
            if existing:
                skipped += 1
                continue

            db.add(
                Student(
                    student_code=student_code,
                    full_name=full_name,
                    class_name=class_name,
                    face_status="unregistered",
                    data_source="real",
                    is_demo=False,
                    registration_method=None,
                )
            )
            inserted += 1

        db.commit()
        total = db.query(func.count(Student.id)).scalar()
        print(f"Class used: {class_name}")
        print(f"Inserted: {inserted}")
        print(f"Skipped existing: {skipped}")
        print(f"Total students now: {total}")
    finally:
        db.close()


if __name__ == "__main__":
    seed_real_demo_students()
