from datetime import datetime, timedelta

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.attendance import Attendance
from models.session import Session as ClassSession
from models.student import Student
from services.timezone_service import now_in_app_timezone


LATE_THRESHOLD_MINUTES = 15
ATTENDED_STATUSES = {"present", "late", "manual"}
OFFICIAL_ATTENDANCE_BLOCK_MESSAGE = (
    "Mẫu này thuộc dữ liệu demo/Kaggle, không được ghi nhận điểm danh chính thức."
)


CROSS_CLASS_REASON_CODE = "cross_class_requires_manual_confirmation"


def cross_class_attendance_message(student_class: str, session_class: str):
    return (
        f"Sinh viên thuộc lớp {student_class}, khác lớp chính của buổi học {session_class}. "
        "Vui lòng xác nhận thủ công nếu sinh viên có đăng ký/học ghép buổi này."
    )


def is_official_attendance_student(student: Student):
    return (
        student.data_source == "real"
        and not student.is_demo
        and student.face_status == "registered"
    )


def official_attendance_block_reason(student: Student):
    if student.data_source != "real" or student.is_demo:
        return OFFICIAL_ATTENDANCE_BLOCK_MESSAGE
    if student.face_status != "registered":
        return "Sinh viên chưa đăng ký khuôn mặt, không được ghi nhận điểm danh chính thức."
    return None


def get_student_and_session(db: Session, student_code: str, session_id: int):
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found.")

    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found.")

    if not student.class_name:
        raise HTTPException(status_code=400, detail="Student does not have a class assigned.")
    if not session.class_name:
        raise HTTPException(status_code=400, detail="Session does not have a class assigned.")
    if student.class_name != session.class_name:
        # TODO: Sau này nên kiểm tra bằng danh sách đăng ký môn học/session_students thay vì so sánh class_name.
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "class_mismatch",
                "code": CROSS_CLASS_REASON_CODE,
                "message": cross_class_attendance_message(student.class_name, session.class_name),
                "student_class": student.class_name,
                "session_class": session.class_name,
            },
        )

    block_reason = official_attendance_block_reason(student)
    if block_reason:
        raise HTTPException(status_code=403, detail=block_reason)

    return student, session


def calculate_attendance_status(session: ClassSession, check_in_at: datetime):
    if not session.start_time:
        return "present"

    session_start = datetime.combine(session.session_date, session.start_time)
    late_threshold = session_start + timedelta(minutes=LATE_THRESHOLD_MINUTES)
    return "present" if check_in_at <= late_threshold else "late"


def serialize_record(record: Attendance, student: Student):
    return {
        "record_id": record.id,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "status": record.status,
        "check_in_at": record.check_in_at.isoformat() if record.check_in_at else None,
        "check_out_at": record.check_out_at.isoformat() if record.check_out_at else None,
        "check_in_conf": record.check_in_conf,
        "check_out_conf": record.check_out_conf,
        "check_in_img": record.check_in_img,
        "note": record.note,
    }


def get_session_record(db: Session, student_id: int, session_id: int):
    return (
        db.query(Attendance)
        .filter(Attendance.student_id == student_id, Attendance.session_id == session_id)
        .first()
    )


def already_checked_in_response(record: Attendance, student: Student):
    return {
        "status": "success",
        "message": f"{student.full_name} already checked in for this session.",
        "data": serialize_record(record, student),
    }


def record_checkin(db: Session, student_code: str, session_id: int, confidence=None, image_path=None):
    student, session = get_student_and_session(db, student_code, session_id)
    existing = get_session_record(db, student.id, session_id)

    if existing:
        return already_checked_in_response(existing, student)

    check_in_at = now_in_app_timezone()
    attendance_status = calculate_attendance_status(session, check_in_at)

    record = Attendance(
        student_id=student.id,
        session_id=session_id,
        check_in_at=check_in_at,
        check_in_conf=confidence,
        check_in_img=image_path,
        status=attendance_status,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = get_session_record(db, student.id, session_id)
        if existing:
            return already_checked_in_response(existing, student)
        raise HTTPException(status_code=409, detail="Attendance record already exists.") from exc
    db.refresh(record)

    return {
        "status": "success",
        "message": f"Check-in recorded for {student.full_name}.",
        "data": serialize_record(record, student),
    }


def record_checkout(db: Session, student_code: str, session_id: int, confidence=None):
    student, _session = get_student_and_session(db, student_code, session_id)
    existing = get_session_record(db, student.id, session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="No check-in record found for this session.")

    if existing.check_out_at:
        return {
            "status": "success",
            "message": f"{student.full_name} already checked out for this session.",
            "data": serialize_record(existing, student),
        }

    existing.check_out_at = now_in_app_timezone()
    existing.check_out_conf = confidence
    db.commit()
    db.refresh(existing)

    return {
        "status": "success",
        "message": f"Check-out recorded for {student.full_name}.",
        "data": serialize_record(existing, student),
    }


def _update_manual_record(db: Session, record: Attendance, student: Student, note=None):
    record.status = "manual"
    record.note = note
    db.commit()
    db.refresh(record)
    return {
        "status": "success",
        "message": f"Manual attendance updated for {student.full_name}.",
        "data": serialize_record(record, student),
    }


def record_manual_attendance(db: Session, student_code: str, session_id: int, note=None):
    student, _session = get_student_and_session(db, student_code, session_id)
    existing = get_session_record(db, student.id, session_id)

    if existing:
        return _update_manual_record(db, existing, student, note)

    record = Attendance(
        student_id=student.id,
        session_id=session_id,
        check_in_at=now_in_app_timezone(),
        status="manual",
        note=note,
    )
    db.add(record)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = get_session_record(db, student.id, session_id)
        if existing:
            return _update_manual_record(db, existing, student, note)
        raise HTTPException(status_code=409, detail="Attendance record already exists.") from exc
    db.refresh(record)

    return {
        "status": "success",
        "message": f"Manual attendance recorded for {student.full_name}.",
        "data": serialize_record(record, student),
    }


def get_session_attendance(db: Session, session_id: int):
    records = db.query(Attendance).filter(Attendance.session_id == session_id).all()
    student_map = {
        student.id: student
        for student in db.query(Student)
        .join(Attendance, Attendance.student_id == Student.id)
        .filter(Attendance.session_id == session_id)
        .all()
    }
    return [
        serialize_record(record, student_map[record.student_id])
        for record in records
        if record.student_id in student_map
    ]


def get_class_attendance_summary(db: Session, class_name: str):
    students = db.query(Student).filter(Student.class_name == class_name).order_by(Student.full_name.asc()).all()
    sessions = (
        db.query(ClassSession)
        .filter(ClassSession.class_name == class_name)
        .order_by(ClassSession.session_date.asc())
        .all()
    )

    result = []
    for student in students:
        records = (
            db.query(Attendance)
            .join(ClassSession, Attendance.session_id == ClassSession.id)
            .filter(Attendance.student_id == student.id, ClassSession.class_name == class_name)
            .all()
        )
        attended = len(
            {
                record.session_id
                for record in records
                if record.session_id is not None and record.status in ATTENDED_STATUSES
            }
        )
        total_sessions = len(sessions)
        absent = max(total_sessions - attended, 0)
        rate = (attended / total_sessions) if total_sessions else 0.0
        result.append(
            {
                "student_code": student.student_code,
                "full_name": student.full_name,
                "class_name": student.class_name,
                "attended": attended,
                "absent": absent,
                "total_sessions": total_sessions,
                "rate": round(rate, 4),
            }
        )

    return result
