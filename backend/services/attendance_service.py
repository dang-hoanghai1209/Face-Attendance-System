from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.attendance import Attendance
from models.attendance_scan import AttendanceScan
from models.enrollment import Enrollment
from models.recognition_attempt import RecognitionAttempt
from models.session import Session as ClassSession
from models.student import Student
from services.timezone_service import now_in_app_timezone


EARLY_CHECKIN_MINUTES = 5
PRESENT_WINDOW_MINUTES = 1
LATE_THRESHOLD_MINUTES = 10
ATTENDED_STATUSES = {"present", "late", "manual", "left_early"}
OFFICIAL_ATTENDANCE_BLOCK_MESSAGE = (
    "Mẫu này thuộc dữ liệu demo/Kaggle, không được ghi nhận điểm danh chính thức."
)


CROSS_CLASS_LEGACY_CODE = "cross_class_requires_manual_confirmation"
CROSS_CLASS_REASON_CODE = "class_mismatch"
MANUAL_CONFIRMABLE_AUDIT_STATUSES = {
    CROSS_CLASS_REASON_CODE,
    CROSS_CLASS_LEGACY_CODE,
    "success",
    "uncertain",
}


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


def attendance_error(status_code: int, code: str, message: str, **extra):
    raise HTTPException(
        status_code=status_code,
        detail={
            "status": code,
            "message": message,
            **extra,
        },
    )


def _get_student_and_session_base(db: Session, student_code: str, session_id: int):
    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")

    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy buổi học.")

    if not student.class_name:
        raise HTTPException(status_code=400, detail="Sinh viên chưa được gán lớp.")
    if not session.class_name:
        raise HTTPException(status_code=400, detail="Buổi học chưa được gán lớp.")

    return student, session


def get_student_and_session(db: Session, student_code: str, session_id: int):
    student, session = _get_student_and_session_base(db, student_code, session_id)
    if session.section_id:
        enrollment = (
            db.query(Enrollment)
            .filter(
                Enrollment.course_section_id == session.section_id,
                Enrollment.student_id == student.id,
                Enrollment.status == "active",
            )
            .first()
        )
        if not enrollment:
            attendance_error(
                403,
                "not_enrolled",
                "Bạn không có trong danh sách đăng ký của lớp học phần này.",
            )
    elif student.class_name != session.class_name:
        # TODO: Sau này nên kiểm tra bằng danh sách đăng ký môn học/session_students thay vì so sánh class_name.
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "class_mismatch",
                "code": CROSS_CLASS_LEGACY_CODE,
                "message": cross_class_attendance_message(student.class_name, session.class_name),
                "student_class": student.class_name,
                "session_class": session.class_name,
            },
        )

    block_reason = official_attendance_block_reason(student)
    if block_reason:
        raise HTTPException(status_code=403, detail=block_reason)

    return student, session


def validate_cross_class_manual_audit(db: Session, student: Student, session: ClassSession, audit_id: int | None):
    if not audit_id:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "missing_recognition_audit",
                "message": "Thiếu audit_id để xác nhận thủ công cho trường hợp sinh viên khác lớp.",
            },
        )

    attempt = db.query(RecognitionAttempt).filter(RecognitionAttempt.id == audit_id).first()
    if not attempt:
        raise HTTPException(
            status_code=404,
            detail={
                "reason": "recognition_audit_not_found",
                "message": "Không tìm thấy bản ghi kiểm tra nhận diện.",
            },
        )

    if attempt.session_id != session.id:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "audit_session_mismatch",
                "message": "Bản ghi nhận diện không thuộc buổi học hiện tại.",
            },
        )

    audit_student_matches = (
        attempt.predicted_student_id == student.id
        or attempt.predicted_student_code == student.student_code
    )
    if not audit_student_matches:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "audit_student_mismatch",
                "message": "Bản ghi nhận diện không khớp với sinh viên cần xác nhận.",
            },
        )

    if attempt.status not in MANUAL_CONFIRMABLE_AUDIT_STATUSES:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "invalid_recognition_audit",
                "message": "Trạng thái bản ghi nhận diện không hợp lệ để xác nhận thủ công sinh viên khác lớp.",
                "audit_status": attempt.status,
            },
        )

    if attempt.confidence is None:
        raise HTTPException(
            status_code=400,
            detail={
                "reason": "missing_audit_confidence",
                "message": "Bản ghi nhận diện thiếu điểm tin cậy.",
            },
        )

    return attempt

def calculate_attendance_status(session: ClassSession, check_in_at: datetime):
    if not session.start_time:
        return "present"

    session_start = datetime.combine(session.session_date, session.start_time)
    present_deadline = session_start + timedelta(minutes=PRESENT_WINDOW_MINUTES)
    return "present" if check_in_at <= present_deadline else "late"


def validate_checkin_window(session: ClassSession, check_in_at: datetime):
    if not session.start_time:
        attendance_error(400, "session_time_missing", "Buổi học chưa được cấu hình thời gian bắt đầu.")

    session_start = datetime.combine(session.session_date, session.start_time)
    attendance_open_at = session_start - timedelta(minutes=EARLY_CHECKIN_MINUTES)
    attendance_deadline = session_start + timedelta(minutes=LATE_THRESHOLD_MINUTES)
    if check_in_at < attendance_open_at:
        attendance_error(
            400,
            "not_started",
            "Buổi học chưa bắt đầu. Vui lòng quay lại khi đến giờ học.",
        )
    if check_in_at > attendance_deadline:
        attendance_error(403, "attendance_closed", "Đã quá thời gian điểm danh.")


def haversine_distance_meters(lat1, lng1, lat2, lng2):
    earth_radius_meters = 6_371_000
    lat1_rad, lng1_rad, lat2_rad, lng2_rad = map(radians, [lat1, lng1, lat2, lng2])
    delta_lat = lat2_rad - lat1_rad
    delta_lng = lng2_rad - lng1_rad
    value = sin(delta_lat / 2) ** 2 + cos(lat1_rad) * cos(lat2_rad) * sin(delta_lng / 2) ** 2
    return 2 * earth_radius_meters * asin(sqrt(value))


def validate_gps(db: Session, session: ClassSession, gps_lat=None, gps_lng=None, gps_accuracy=None):
    if session.latitude is None or session.longitude is None:
        attendance_error(403, "session_gps_missing", "Buổi học chưa cấu hình tọa độ GPS")

    if gps_lat is None or gps_lng is None:
        attendance_error(400, "gps_missing", "Vui lòng cho phép truy cập vị trí GPS để điểm danh.")

    allowed_radius_meters = session.radius_meters if session.radius_meters is not None else 50
    distance_meters = haversine_distance_meters(gps_lat, gps_lng, session.latitude, session.longitude)
    if distance_meters > allowed_radius_meters:
        attendance_error(
            403,
            "gps_out_of_range",
            "Ngoài phạm vi lớp học",
            distance_meters=round(distance_meters, 2),
            allowed_radius_meters=allowed_radius_meters,
        )

    return {
        "gps_lat": gps_lat,
        "gps_lng": gps_lng,
        "gps_accuracy": gps_accuracy,
        "distance_meters": round(distance_meters, 2),
        "allowed_radius_meters": allowed_radius_meters,
    }


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
        "gps_lat": record.gps_lat,
        "gps_lng": record.gps_lng,
        "gps_accuracy": record.gps_accuracy,
        "distance_meters": record.distance_meters,
        "liveness_passed": record.liveness_passed,
        "scan_count": record.scan_count,
        "last_scan_at": record.last_scan_at.isoformat() if record.last_scan_at else None,
        "note": record.note,
    }


def flatten_checkin_response(status: str, message: str, record: Attendance, student: Student, allowed_radius_meters=None):
    data = serialize_record(record, student)
    return {
        "status": status,
        "message": message,
        "student_code": student.student_code,
        "full_name": student.full_name,
        "confidence": record.check_in_conf,
        "distance_meters": record.distance_meters,
        "allowed_radius_meters": allowed_radius_meters,
        "check_in_time": record.check_in_at.isoformat() if record.check_in_at else None,
        "data": data,
    }


def get_session_record(db: Session, student_id: int, session_id: int):
    return (
        db.query(Attendance)
        .filter(Attendance.student_id == student_id, Attendance.session_id == session_id)
        .first()
    )


def allowed_radius_for_session(db: Session, session: ClassSession):
    if not session:
        return None
    return session.radius_meters


def next_scan_index(db: Session, record: Attendance):
    persisted_scan_count = db.query(AttendanceScan).filter(AttendanceScan.attendance_id == record.id).count()
    return max(record.scan_count or 0, persisted_scan_count) + 1


def create_attendance_scan(
    db: Session,
    record: Attendance,
    *,
    scanned_at: datetime,
    confidence=None,
    gps_lat=None,
    gps_lng=None,
    liveness_passed=None,
    note=None,
):
    scan_index = next_scan_index(db, record)
    record.scan_count = scan_index
    record.last_scan_at = scanned_at
    scan = AttendanceScan(
        attendance_id=record.id,
        scanned_at=scanned_at,
        confidence=confidence,
        gps_lat=gps_lat,
        gps_lng=gps_lng,
        liveness_passed=liveness_passed,
        scan_index=scan_index,
        note=note,
    )
    db.add(scan)
    return scan


def already_checked_in_response(record: Attendance, student: Student, session: ClassSession | None = None, db: Session | None = None):
    return flatten_checkin_response(
        "success",
        "Điểm danh thành công.",
        record,
        student,
        allowed_radius_for_session(db, session) if db is not None and session is not None else None,
    )


def record_checkin(
    db: Session,
    student_code: str,
    session_id: int,
    confidence=None,
    image_path=None,
    gps_lat=None,
    gps_lng=None,
    gps_accuracy=None,
    liveness_passed=None,
):
    student, session = get_student_and_session(db, student_code, session_id)
    existing = get_session_record(db, student.id, session_id)

    check_in_at = now_in_app_timezone()
    validate_checkin_window(session, check_in_at)
    gps_data = validate_gps(db, session, gps_lat=gps_lat, gps_lng=gps_lng, gps_accuracy=gps_accuracy) or {}

    if existing:
        if existing.status in {"present", "late"}:
            existing.status = "left_early"
            scan_note = "marked_left_early"
        elif existing.status == "left_early":
            existing.status = calculate_attendance_status(session, existing.check_in_at or check_in_at)
            scan_note = "restored_attendance"
        else:
            scan_note = "manual_unchanged"

        create_attendance_scan(
            db,
            existing,
            scanned_at=check_in_at,
            confidence=confidence,
            gps_lat=gps_data.get("gps_lat"),
            gps_lng=gps_data.get("gps_lng"),
            liveness_passed=liveness_passed,
            note=scan_note,
        )
        db.commit()
        db.refresh(existing)
        return already_checked_in_response(existing, student, session, db)

    record = Attendance(
        student_id=student.id,
        session_id=session_id,
        check_in_at=check_in_at,
        check_in_conf=confidence,
        check_in_img=image_path,
        gps_lat=gps_data.get("gps_lat"),
        gps_lng=gps_data.get("gps_lng"),
        gps_accuracy=gps_data.get("gps_accuracy"),
        distance_meters=gps_data.get("distance_meters"),
        liveness_passed=liveness_passed if liveness_passed is not None else False,
        status=calculate_attendance_status(session, check_in_at),
    )
    db.add(record)
    try:
        db.flush()
        create_attendance_scan(
            db,
            record,
            scanned_at=check_in_at,
            confidence=confidence,
            gps_lat=gps_data.get("gps_lat"),
            gps_lng=gps_data.get("gps_lng"),
            liveness_passed=liveness_passed,
            note="check_in",
        )
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        existing = get_session_record(db, student.id, session_id)
        if existing:
            return record_checkin(
                db,
                student_code=student_code,
                session_id=session_id,
                confidence=confidence,
                image_path=image_path,
                gps_lat=gps_lat,
                gps_lng=gps_lng,
                gps_accuracy=gps_accuracy,
                liveness_passed=liveness_passed,
            )
        raise HTTPException(status_code=409, detail="Bản ghi điểm danh đã tồn tại.") from exc
    db.refresh(record)

    return flatten_checkin_response(
        "success",
        "Điểm danh thành công.",
        record,
        student,
        gps_data.get("allowed_radius_meters"),
    )


def record_checkout(db: Session, student_code: str, session_id: int, confidence=None):
    student, _session = get_student_and_session(db, student_code, session_id)
    existing = get_session_record(db, student.id, session_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Không tìm thấy bản ghi vào lớp cho buổi học này.")

    if existing.check_out_at:
        return {
            "status": "success",
            "message": f"{student.full_name} đã được ghi nhận ra về cho buổi học này.",
            "data": serialize_record(existing, student),
        }

    existing.check_out_at = now_in_app_timezone()
    existing.check_out_conf = confidence
    db.commit()
    db.refresh(existing)

    return {
        "status": "success",
        "message": f"Đã ghi nhận ra về cho {student.full_name}.",
        "data": serialize_record(existing, student),
    }


def _update_manual_record(db: Session, record: Attendance, student: Student, note=None, confidence=None):
    record.status = "manual"
    record.note = note
    if confidence is not None and record.check_in_conf is None:
        record.check_in_conf = confidence
    db.commit()
    db.refresh(record)
    return {
        "status": "success",
        "message": f"Đã cập nhật điểm danh thủ công cho {student.full_name}.",
        "data": serialize_record(record, student),
    }


def record_manual_attendance(db: Session, student_code: str, session_id: int, note=None, audit_id: int | None = None):
    student, session = _get_student_and_session_base(db, student_code, session_id)

    block_reason = official_attendance_block_reason(student)
    if block_reason:
        raise HTTPException(status_code=403, detail=block_reason)

    recognition_confidence = None
    if student.class_name != session.class_name:
        attempt = validate_cross_class_manual_audit(db, student, session, audit_id)
        recognition_confidence = attempt.confidence

    existing = get_session_record(db, student.id, session_id)

    if existing:
        return _update_manual_record(db, existing, student, note, recognition_confidence)

    record = Attendance(
        student_id=student.id,
        session_id=session_id,
        check_in_at=now_in_app_timezone(),
        check_in_conf=recognition_confidence,
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
            return _update_manual_record(db, existing, student, note, recognition_confidence)
        raise HTTPException(status_code=409, detail="Bản ghi điểm danh đã tồn tại.") from exc
    db.refresh(record)

    return {
        "status": "success",
        "message": f"Đã ghi nhận điểm danh thủ công cho {student.full_name}.",
        "data": serialize_record(record, student),
    }


def delete_attendance_record(db: Session, attendance_id: int):
    record = db.query(Attendance).filter(Attendance.id == attendance_id).first()
    if not record:
        raise HTTPException(
            status_code=404,
            detail={
                "reason": "attendance_record_not_found",
                "message": f"Không tìm thấy bản ghi điểm danh #{attendance_id}.",
            },
        )

    student = db.query(Student).filter(Student.id == record.student_id).first()
    deleted = {
        "record_id": record.id,
        "student_code": student.student_code if student else None,
        "full_name": student.full_name if student else None,
        "session_id": record.session_id,
    }
    db.query(AttendanceScan).filter(AttendanceScan.attendance_id == record.id).delete(synchronize_session=False)
    db.delete(record)
    db.commit()

    return {
        "status": "success",
        "message": "Đã xóa bản ghi điểm danh.",
        "data": deleted,
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
