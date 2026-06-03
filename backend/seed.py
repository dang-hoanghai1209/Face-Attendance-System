import os
import pickle

from sqlalchemy.orm import Session

from database import Base, engine
from models.student import Student
from services.class_service import lfw_class_for_student_code


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
EMBEDDING_DB_PATH = os.path.join(BASE_DIR, "data", "embedding_db.pkl")


def seed_data():
    Base.metadata.create_all(bind=engine)

    try:
        with open(EMBEDDING_DB_PATH, "rb") as db_file:
            db_data = pickle.load(db_file)
    except Exception as exc:
        print(f"Cannot read embedding database: {exc}")
        return

    print("Seeding from embedding_db.pkl is intended for legacy/dev bootstrap only.")

    db = Session(bind=engine)
    inserted = 0

    try:
        for student_code in db_data.keys():
            existing = db.query(Student).filter(Student.student_code == student_code).first()
            if existing:
                continue

            db.add(
                Student(
                    student_code=student_code,
                    full_name=student_code.replace("_", " "),
                    class_name=lfw_class_for_student_code(student_code) or "63LFW",
                    data_source="kaggle",
                    registration_method="import",
                    is_demo=True,
                )
            )
            inserted += 1

        db.commit()
        print(f"Inserted {inserted} students from embedding_db.pkl.")
    finally:
        db.close()


if __name__ == "__main__":
    seed_data()
