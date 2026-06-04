from datetime import datetime

from fastapi import HTTPException
from sqlalchemy import func
from sqlalchemy.orm import Session

from models.attendance import Attendance
from models.session import Session as ClassSession
from models.student import Student


ATTENDED_STATUSES = {"present", "late", "manual"}
STATUS_PRIORITY = {"manual": 3, "present": 2, "late": 1}


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
        manual = sum(1 for record in effective_records if record.status == "manual")
        absent = max(total_sessions - attended, 0)
        rate = (attended / total_sessions) if total_sessions > 0 else 0
        result.append(
            {
                "student_code": student.student_code,
                "full_name": student.full_name,
                "class_name": student.class_name,
                "present": present,
                "late": late,
                "manual": manual,
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
        raise HTTPException(status_code=404, detail="Session not found.")

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

    class_student_ids = {student.id for student in students}
    cross_class_student_ids = [
        student_id
        for student_id in attendance_map
        if student_id not in class_student_ids
    ]
    if cross_class_student_ids:
        cross_class_students = (
            db.query(Student)
            .filter(Student.id.in_(cross_class_student_ids), *official_student_filter())
            .order_by(Student.full_name.asc())
            .all()
        )
        for student in cross_class_students:
            record = attendance_map.get(student.id)
            if not record:
                continue
            report_rows.append(
                {
                    "record_id": record.id,
                    "student_code": student.student_code,
                    "full_name": student.full_name,
                    "class_name": student.class_name,
                    "subject": session.subject,
                    "session_date": session.session_date.isoformat() if session.session_date else None,
                    "start_time": session.start_time.isoformat() if session.start_time else None,
                    "end_time": session.end_time.isoformat() if session.end_time else None,
                    "status": record.status,
                    "check_in_at": record.check_in_at.isoformat() if record.check_in_at else None,
                    "check_out_at": record.check_out_at.isoformat() if record.check_out_at else None,
                    "check_in_conf": record.check_in_conf,
                    "check_out_conf": record.check_out_conf,
                    "note": record.note,
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
