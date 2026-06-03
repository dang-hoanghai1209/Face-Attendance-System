VALID_CLASS_NAMES = (
    "63TTQL",
    "63HTTT",
    "63CNTT",
    "63LFW",
    "64TTQL",
    "64HTTT",
    "64CNTT",
    "64LFW",
)

VALID_CLASS_SET = set(VALID_CLASS_NAMES)
LEGACY_MIS_CLASS = "MIS"


def lfw_class_for_student_code(student_code):
    code = (student_code or "").strip()
    if code.startswith("63"):
        return "63LFW"
    if code.startswith("64"):
        return "64LFW"
    return None


def student_code_matches_class(student_code, class_name):
    if not student_code or not class_name:
        return True
    if class_name not in VALID_CLASS_SET:
        return False
    return class_name.startswith(student_code[:2])


def migrate_mis_students_to_lfw(db, dry_run=True):
    from models.student import Student

    students = (
        db.query(Student)
        .filter(Student.class_name == LEGACY_MIS_CLASS)
        .order_by(Student.student_code.asc())
        .all()
    )

    migrated = []
    skipped = []
    for student in students:
        target_class = lfw_class_for_student_code(student.student_code)
        if not target_class:
            skipped.append(
                {
                    "id": student.id,
                    "student_code": student.student_code,
                    "full_name": student.full_name,
                    "reason": "student_code does not start with 63 or 64",
                }
            )
            continue

        migrated.append(
            {
                "id": student.id,
                "student_code": student.student_code,
                "from_class": student.class_name,
                "to_class": target_class,
            }
        )
        if not dry_run:
            student.class_name = target_class

    if not dry_run:
        db.commit()

    return {
        "dry_run": dry_run,
        "migrated_count": len(migrated),
        "skipped_count": len(skipped),
        "migrated": migrated,
        "skipped": skipped,
    }
