from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from models.attendance import Attendance
from models.course_section import CourseSection
from models.enrollment import Enrollment
from models.session import Session as ClassSession
from models.student import Student
from services.auth_service import resolve_student_for_user


ATTENDED_STATUSES = {"present", "late", "left_early"}
STATUS_PRIORITY = {"present": 3, "late": 2, "left_early": 1}


def official_student_filter():
    return Student.data_source == "real", Student.is_demo.is_(False)


def record_rank(record: Attendance):
    return (
        -STATUS_PRIORITY.get(record.status, 0),
        record.check_in_at is None,
        record.check_in_at or record.created_at or datetime.max,
        record.id or 0,
    )


def best_records_by(records, field_name: str):
    best_records = {}
    for record in records:
        key = getattr(record, field_name)
        if key is None:
            continue

        current = best_records.get(key)
        if current is None or record_rank(record) < record_rank(current):
            best_records[key] = record

    return best_records


def build_class_summary(class_name: str, db: Session):
    students = (
        db.query(Student)
        .filter(Student.class_name == class_name, *official_student_filter())
        .order_by(Student.full_name.asc())
        .all()
    )
    if not students:
        return []

    total_sessions = db.query(ClassSession).filter(ClassSession.class_name == class_name).count()
    result = []

    for student in students:
        records = (
            db.query(Attendance)
            .join(ClassSession, Attendance.session_id == ClassSession.id)
            .filter(Attendance.student_id == student.id, ClassSession.class_name == class_name)
            .all()
        )
        effective_records = best_records_by(records, "session_id").values()
        attended = sum(1 for record in effective_records if record.status in ATTENDED_STATUSES)
        present = sum(1 for record in effective_records if record.status == "present")
        late = sum(1 for record in effective_records if record.status == "late")
        absent = max(total_sessions - attended, 0)
        rate = (attended / total_sessions) if total_sessions > 0 else 0
        result.append(
            {
                "student_code": student.student_code,
                "full_name": student.full_name,
                "class_name": student.class_name,
                "present": present,
                "late": late,
                "absent": absent,
                "attended": attended,
                "total_sessions": total_sessions,
                "rate": round(rate, 4),
                "warning": rate < 0.8 if total_sessions > 0 else False,
            }
        )

    return result


def build_session_report(session_id: int, db: Session):
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy buổi học.")

    if session.section_id:
        students = (
            db.query(Student)
            .join(Enrollment, Enrollment.student_id == Student.id)
            .filter(
                Enrollment.course_section_id == session.section_id,
                Enrollment.status == "active",
                *official_student_filter(),
            )
            .order_by(Student.full_name.asc())
            .all()
        )
    else:
        students = (
            db.query(Student)
            .filter(Student.class_name == session.class_name, *official_student_filter())
            .order_by(Student.full_name.asc())
            .all()
        )
    attendance_records = (
        db.query(Attendance)
        .join(Student, Attendance.student_id == Student.id)
        .filter(Attendance.session_id == session_id, *official_student_filter())
        .all()
    )
    attendance_map = best_records_by(attendance_records, "student_id")

    report_rows = []
    for student in students:
        record = attendance_map.get(student.id)
        report_rows.append(
            {
                "record_id": record.id if record else None,
                "student_code": student.student_code,
                "full_name": student.full_name,
                "class_name": student.class_name,
                "subject": session.subject,
                "session_date": session.session_date.isoformat() if session.session_date else None,
                "start_time": session.start_time.isoformat() if session.start_time else None,
                "end_time": session.end_time.isoformat() if session.end_time else None,
                "status": record.status if record else "absent",
                "check_in_at": record.check_in_at.isoformat() if record and record.check_in_at else None,
                "check_out_at": record.check_out_at.isoformat() if record and record.check_out_at else None,
                "check_in_conf": record.check_in_conf if record else None,
                "check_out_conf": record.check_out_conf if record else None,
                "note": record.note if record else None,
            }
        )

    return session, report_rows


def get_dashboard_stats(db: Session):
    total_students = db.query(Student).filter(*official_student_filter()).count()
    registered_faces = (
        db.query(Student)
        .filter(*official_student_filter(), Student.face_status == "registered")
        .count()
    )
    unregistered_faces = max(total_students - registered_faces, 0)
    class_sessions = db.query(ClassSession).count()

    if total_students == 0:
        return {
            "total_students": 0,
            "registered_faces": 0,
            "unregistered_faces": 0,
            "total_sessions": class_sessions,
            "avg_attendance_rate": 0,
            "warning_count": 0,
            "pie_data": [{"name": "Present", "value": 0}, {"name": "Absent", "value": 0}],
        }

    sessions_per_class = {
        row.class_name: row.cnt
        for row in db.query(ClassSession.class_name, func.count(ClassSession.id).label("cnt"))
        .group_by(ClassSession.class_name)
        .all()
    }

    attended_per_student = {
        row.student_id: row.cnt
        for row in db.query(
            Attendance.student_id,
            func.count(func.distinct(Attendance.session_id)).label("cnt"),
        )
        .join(Student, Attendance.student_id == Student.id)
        .join(ClassSession, Attendance.session_id == ClassSession.id)
        .filter(Student.class_name == ClassSession.class_name)
        .filter(*official_student_filter())
        .filter(Attendance.status.in_(ATTENDED_STATUSES))
        .group_by(Attendance.student_id)
        .all()
    }

    students = db.query(Student.id, Student.class_name).filter(*official_student_filter()).all()
    total_expected = 0
    total_attended = 0
    warning_count = 0

    for student_id, class_name in students:
        session_count = sessions_per_class.get(class_name, 0)
        attended_count = attended_per_student.get(student_id, 0)
        total_expected += session_count
        total_attended += attended_count
        if session_count > 0 and (attended_count / session_count) < 0.8:
            warning_count += 1

    total_absent = max(total_expected - total_attended, 0)
    avg_rate = (total_attended / total_expected) if total_expected > 0 else 0

    return {
        "total_students": total_students,
        "registered_faces": registered_faces,
        "unregistered_faces": unregistered_faces,
        "total_sessions": class_sessions,
        "avg_attendance_rate": round(avg_rate, 2),
        "warning_count": warning_count,
        "pie_data": [
            {"name": "Present", "value": total_attended},
            {"name": "Absent", "value": total_absent},
        ],
    }


def _identity_values(user):
    values = {getattr(user, "username", None), getattr(user, "full_name", None)}
    return [value for value in values if value]


def _owned_session_query(db: Session, user):
    identities = _identity_values(user)
    if user.role in {"admin", "viewer"}:
        return db.query(ClassSession)
    if not identities:
        return db.query(ClassSession).filter(False)

    return (
        db.query(ClassSession)
        .outerjoin(CourseSection, ClassSession.section_id == CourseSection.id)
        .filter(
            or_(
                ClassSession.created_by.in_(identities),
                CourseSection.lecturer_name.in_(identities),
            )
        )
    )


def get_dashboard_stats_for_user(db: Session, user):
    if user.role in {"admin", "viewer"}:
        return get_dashboard_stats(db)

    if user.role == "student":
        student = resolve_student_for_user(db, user)
        if not student:
            return {
                "total_students": 0,
                "registered_faces": 0,
                "unregistered_faces": 0,
                "total_sessions": 0,
                "avg_attendance_rate": 0,
                "warning_count": 0,
                "pie_data": [{"name": "Present", "value": 0}, {"name": "Absent", "value": 0}],
            }

        session_ids = [
            row.id
            for row in (
                db.query(ClassSession.id)
                .join(Enrollment, Enrollment.course_section_id == ClassSession.section_id)
                .filter(Enrollment.student_id == student.id, Enrollment.status == "active")
                .filter(ClassSession.section_id.isnot(None))
                .distinct()
                .all()
            )
        ]
        total_sessions = len(session_ids)
        attended = (
            db.query(func.count(func.distinct(Attendance.session_id)))
            .filter(
                Attendance.student_id == student.id,
                Attendance.session_id.in_(session_ids) if session_ids else False,
                Attendance.status.in_(ATTENDED_STATUSES),
            )
            .scalar()
            or 0
        )
        absent = max(total_sessions - attended, 0)
        rate = (attended / total_sessions) if total_sessions > 0 else 0
        return {
            "total_students": 1,
            "registered_faces": 1 if student.face_status == "registered" else 0,
            "unregistered_faces": 0 if student.face_status == "registered" else 1,
            "total_sessions": total_sessions,
            "avg_attendance_rate": round(rate, 2),
            "warning_count": 1 if total_sessions > 0 and rate < 0.8 else 0,
            "pie_data": [
                {"name": "Present", "value": attended},
                {"name": "Absent", "value": absent},
            ],
        }

    owned_sessions = _owned_session_query(db, user)
    owned_session_ids = [row.id for row in owned_sessions.with_entities(ClassSession.id).all()]
    if not owned_session_ids:
        return {
            "total_students": 0,
            "registered_faces": 0,
            "unregistered_faces": 0,
            "total_sessions": 0,
            "avg_attendance_rate": 0,
            "warning_count": 0,
            "pie_data": [{"name": "Present", "value": 0}, {"name": "Absent", "value": 0}],
        }

    student_ids = [
        row.student_id
        for row in (
            db.query(Enrollment.student_id)
            .join(ClassSession, ClassSession.section_id == Enrollment.course_section_id)
            .filter(Enrollment.status == "active", ClassSession.id.in_(owned_session_ids))
            .distinct()
            .all()
        )
    ]
    total_students = len(student_ids)
    registered_faces = (
        db.query(Student)
        .filter(Student.id.in_(student_ids), Student.face_status == "registered")
        .count()
        if student_ids
        else 0
    )
    unregistered_faces = max(total_students - registered_faces, 0)
    total_sessions = len(owned_session_ids)
    attended = (
        db.query(func.count(func.distinct(Attendance.id)))
        .filter(
            Attendance.session_id.in_(owned_session_ids),
            Attendance.status.in_(ATTENDED_STATUSES),
        )
        .scalar()
        or 0
    )
    total_expected = total_students * total_sessions
    warning_count = 0
    if total_sessions > 0:
        attendance_counts = {
            row.student_id: row.cnt
            for row in (
                db.query(Attendance.student_id, func.count(func.distinct(Attendance.session_id)).label("cnt"))
                .filter(Attendance.session_id.in_(owned_session_ids), Attendance.status.in_(ATTENDED_STATUSES))
                .group_by(Attendance.student_id)
                .all()
            )
        }
        warning_count = sum(1 for student_id in student_ids if total_sessions > 0 and (attendance_counts.get(student_id, 0) / total_sessions) < 0.8)

    rate = (attended / total_expected) if total_expected > 0 else 0
    return {
        "total_students": total_students,
        "registered_faces": registered_faces,
        "unregistered_faces": unregistered_faces,
        "total_sessions": total_sessions,
        "avg_attendance_rate": round(rate, 2),
        "warning_count": warning_count,
        "pie_data": [
            {"name": "Present", "value": attended},
            {"name": "Absent", "value": max(total_expected - attended, 0)},
        ],
    }


def user_can_access_class_report(db: Session, user, class_name: str) -> bool:
    if user.role in {"admin", "viewer"}:
        return True
    if user.role == "student":
        return False

    identities = _identity_values(user)
    if not identities:
        return False

    return (
        db.query(ClassSession.id)
        .outerjoin(CourseSection, ClassSession.section_id == CourseSection.id)
        .filter(
            ClassSession.class_name == class_name,
            or_(
                ClassSession.created_by.in_(identities),
                CourseSection.lecturer_name.in_(identities),
            ),
        )
        .first()
        is not None
    )


def build_class_summary_for_user(class_name: str, db: Session, user):
    if not user_can_access_class_report(db, user, class_name):
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem báo cáo lớp học này.")
    return build_class_summary(class_name, db)


def build_session_report_for_user(session_id: int, db: Session, user):
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy buổi học.")

    if user.role in {"admin", "viewer"}:
        return build_session_report(session_id, db)

    if user.role == "student":
        student = resolve_student_for_user(db, user)
        if not student:
            raise HTTPException(status_code=404, detail="Không tìm thấy hồ sơ sinh viên.")
        _session, report_rows = build_session_report(session_id, db)
        return _session, [row for row in report_rows if row["student_code"] == student.student_code]

    identities = _identity_values(user)
    owns_session = (
        db.query(ClassSession.id)
        .outerjoin(CourseSection, ClassSession.section_id == CourseSection.id)
        .filter(
            ClassSession.id == session_id,
            or_(
                ClassSession.created_by.in_(identities),
                CourseSection.lecturer_name.in_(identities),
            ),
        )
        .first()
        is not None
    )
    if not owns_session:
        raise HTTPException(status_code=403, detail="Bạn không có quyền xem báo cáo buổi học này.")
    return build_session_report(session_id, db)
