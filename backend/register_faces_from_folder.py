from pathlib import Path

from dotenv import load_dotenv


BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

from database import SessionLocal
from face_service import (
    aggregate_embeddings,
    count_faces_in_image_bytes,
    image_bytes_to_embedding,
    replace_student_embeddings,
)
from models.student import Student


ENROLLMENT_DIR = BASE_DIR / "enrollment_data"
CLASS_NAME = "LFW_TEST"
MIN_VALID_EMBEDDINGS = 5
IMAGE_EXTENSIONS = {".jpg", ".png"}


def list_student_dirs():
    if not ENROLLMENT_DIR.exists():
        return []

    return sorted(path for path in ENROLLMENT_DIR.iterdir() if path.is_dir())


def list_images(student_dir):
    return sorted(
        path
        for path in student_dir.iterdir()
        if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
    )


def get_or_create_student(db, student_code):
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if student:
        student.data_source = "lfw"
        student.registration_method = "lfw_import"
        student.is_demo = True
        db.commit()
        return student

    student = Student(
        student_code=student_code,
        full_name=student_code.replace("_", " "),
        class_name=CLASS_NAME,
        face_status="unregistered",
        data_source="lfw",
        registration_method="lfw_import",
        is_demo=True,
    )
    db.add(student)
    db.commit()
    db.refresh(student)
    return student


def collect_embeddings(image_paths):
    embeddings = []
    stats = {
        "images_read": 0,
        "accepted": 0,
        "invalid_image": 0,
        "no_face": 0,
        "multiple_faces": 0,
        "embedding_failed": 0,
    }

    for image_path in image_paths:
        try:
            image_bytes = image_path.read_bytes()
            stats["images_read"] += 1
            face_count = count_faces_in_image_bytes(image_bytes)
        except Exception as exc:
            stats["invalid_image"] += 1
            print(f"  skipped {image_path.name}: {exc}")
            continue

        if face_count == 0:
            stats["no_face"] += 1
            print(f"  skipped {image_path.name}: no_face_detected")
            continue

        if face_count > 1:
            stats["multiple_faces"] += 1
            print(f"  skipped {image_path.name}: multiple_faces_detected ({face_count})")
            continue

        try:
            embedding = image_bytes_to_embedding(image_bytes)
        except Exception as exc:
            stats["embedding_failed"] += 1
            print(f"  skipped {image_path.name}: embedding_failed: {exc}")
            continue

        if embedding is None:
            stats["no_face"] += 1
            print(f"  skipped {image_path.name}: no_face_detected")
            continue

        embeddings.append(embedding)
        stats["accepted"] += 1

    return embeddings, stats


def register_student_from_folder(db, student_dir):
    student_code = student_dir.name
    image_paths = list_images(student_dir)
    student = get_or_create_student(db, student_code)
    embeddings, stats = collect_embeddings(image_paths)

    success = len(embeddings) >= MIN_VALID_EMBEDDINGS
    if success:
        mean_embedding = aggregate_embeddings(embeddings)
        replace_student_embeddings(db, student.id, [mean_embedding], source="lfw_folder_mean")
        student.face_status = "registered"
        student.data_source = "lfw"
        student.registration_method = "lfw_import"
        student.is_demo = True
        db.commit()

    print(f"student_code: {student_code}")
    print(f"images_read: {stats['images_read']}")
    print(f"accepted_embeddings: {stats['accepted']}")
    print(f"skipped_no_face: {stats['no_face']}")
    print(f"skipped_multiple_faces: {stats['multiple_faces']}")
    print(f"skipped_invalid_image: {stats['invalid_image']}")
    print(f"skipped_embedding_failed: {stats['embedding_failed']}")
    print(f"registration: {'success' if success else 'failed'}")
    print()

    return success, stats


def main():
    student_dirs = list_student_dirs()
    if not student_dirs:
        print(f"No enrollment folders found in: {ENROLLMENT_DIR}")
        return

    success_count = 0
    failure_count = 0
    total_stats = {
        "images_read": 0,
        "accepted": 0,
        "invalid_image": 0,
        "no_face": 0,
        "multiple_faces": 0,
        "embedding_failed": 0,
    }

    db = SessionLocal()
    try:
        for student_dir in student_dirs:
            try:
                success, stats = register_student_from_folder(db, student_dir)
                for key, value in stats.items():
                    total_stats[key] += value
                if success:
                    success_count += 1
                else:
                    failure_count += 1
            except Exception as exc:
                db.rollback()
                failure_count += 1
                print(f"student_code: {student_dir.name}")
                print("images_read: 0")
                print("faces_detected: 0")
                print("registration: failed")
                print(f"error: {exc}")
                print()
    finally:
        db.close()

    print("Enrollment completed.")
    print(f"successful_students: {success_count}")
    print(f"failed_students: {failure_count}")
    print(f"total_images_read: {total_stats['images_read']}")
    print(f"total_accepted_embeddings: {total_stats['accepted']}")
    print(f"total_skipped_no_face: {total_stats['no_face']}")
    print(f"total_skipped_multiple_faces: {total_stats['multiple_faces']}")
    print(f"total_skipped_invalid_image: {total_stats['invalid_image']}")
    print(f"total_skipped_embedding_failed: {total_stats['embedding_failed']}")


if __name__ == "__main__":
    main()
