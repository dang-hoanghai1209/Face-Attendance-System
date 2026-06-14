from datetime import datetime, timedelta
from math import asin, cos, radians, sin, sqrt

from fastapi import HTTPException
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.attendance import Attendance
from models.attendance_scan import AttendanceScan
from models.enrollment import Enrollment
from models.session import Session as ClassSession
from models.student import Student
from face_service import THRESHOLD_UNCERTAIN
from services.security_alert_service import create_alert
from services.timezone_service import now_in_app_timezone


EARLY_CHECKIN_MINUTES = 15
PRESENT_WINDOW_MINUTES = 1
LATE_THRESHOLD_MINUTES = 10
MIN_SESSION_ENROLLMENTS = 5
MIN_SESSION_ENROLLMENTS_MESSAGE = "Buổi học cần tối thiểu 5 sinh viên đã được đăng ký"
ATTENDED_STATUSES = {"present", "late", "left_early"}
OFFICIAL_ATTENDANCE_BLOCK_MESSAGE = (
    "Mẫu này thuộc dữ liệu demo/Kaggle, không được ghi nhận điểm danh chính thức."
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
            "success": False,
            "reason": code,
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


def get_session_or_404(db: Session, session_id: int):
    session = db.query(ClassSession).filter(ClassSession.id == session_id).first()
    if not session:
        raise HTTPException(status_code=404, detail="Không tìm thấy buổi học.")
    return session


def _is_student_enrolled_in_session(db: Session, student: Student, session: ClassSession):
    filters = [
        (Enrollment.session_id == session.id) & (Enrollment.student_id == student.id)
    ]
    if session.section_id:
        filters.append(
            (Enrollment.course_section_id == session.section_id) & (Enrollment.student_id == student.id) & (Enrollment.status == "active")
        )
    return (
        db.query(Enrollment)
        .filter(or_(*filters))
        .first()
        is not None
    )


def count_session_enrollments(db: Session, session: ClassSession):
    filters = [Enrollment.session_id == session.id]
    if session.section_id:
        filters.append(
            (Enrollment.course_section_id == session.section_id) & (Enrollment.status == "active")
        )
    return (
        db.query(Enrollment.student_id)
        .filter(or_(*filters))
        .distinct()
        .count()
    )


def _is_legacy_enrolled_or_class_match(db: Session, student: Student, session: ClassSession):
    if session.section_id:
        return (
            db.query(Enrollment)
            .filter(
                Enrollment.course_section_id == session.section_id,
                Enrollment.student_id == student.id,
                Enrollment.status == "active",
            )
            .first()
            is not None
        )
    return student.class_name == session.class_name


def _security_alert_response(status: str, message: str, alert):
    return {
        "status": status,
        "success": False,
        "reason": status,
        "message": message,
        "alert_id": alert.id,
        "alert_type": alert.alert_type,
        "session_id": alert.session_id,
        "student_id": alert.student_id,
        "confidence": alert.confidence,
        "liveness_score": alert.liveness_score,
        "captured_img": alert.captured_img,
    }


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
                "Sinh viên không thuộc lớp học phần này",
            )
    elif student.class_name != session.class_name:
        attendance_error(
            403,
            "not_enrolled",
            "Sinh viên không thuộc lớp học phần này",
            student_class=student.class_name,
            session_class=session.class_name,
        )

    block_reason = official_attendance_block_reason(student)
    if block_reason:
        raise HTTPException(status_code=403, detail=block_reason)

    return student, session


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
            "Lớp học chưa bắt đầu điểm danh",
        )
    if check_in_at > attendance_deadline:
        attendance_error(403, "expired", "Lớp học đã kết thúc điểm danh")


def validate_min_session_enrollments(db: Session, session: ClassSession):
    enrollment_count = count_session_enrollments(db, session)
    if 0 < enrollment_count < MIN_SESSION_ENROLLMENTS:
        attendance_error(
            403,
            "insufficient_enrollments",
            MIN_SESSION_ENROLLMENTS_MESSAGE,
            enrollment_count=enrollment_count,
            minimum_required=MIN_SESSION_ENROLLMENTS,
        )
    return enrollment_count


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
            "Ngoài phạm vi điểm danh",
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
        "success": status == "success",
        "reason": None if status == "success" else status,
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
    liveness_score=None,
    recognition_status=None,
):
    session = get_session_or_404(db, session_id)
    normalized_recognition_status = (recognition_status or "").lower()

    if liveness_passed is False:
        alert = create_alert(
            db,
            session_id=session_id,
            alert_type="SPOOF",
            captured_img=image_path,
            confidence=confidence,
            liveness_score=liveness_score,
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            note="Liveness check failed during attendance check-in.",
        )
        return _security_alert_response(
            "spoof",
            "Phát hiện giả mạo khuôn mặt",
            alert,
        )

    if normalized_recognition_status == "unknown" or (
        confidence is not None and confidence < THRESHOLD_UNCERTAIN
    ):
        alert = create_alert(
            db,
            session_id=session_id,
            alert_type="UNKNOWN_FACE",
            captured_img=image_path,
            confidence=confidence,
            liveness_score=liveness_score,
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            note="Unknown face during attendance check-in.",
        )
        return _security_alert_response(
            "unknown",
            "Không nhận diện được khuôn mặt",
            alert,
        )

    student = db.query(Student).filter(Student.student_code == student_code).first()
    if not student:
        raise HTTPException(status_code=404, detail="Không tìm thấy sinh viên.")

    if not student.class_name:
        raise HTTPException(status_code=400, detail="Sinh viên chưa được gán lớp.")
    if not session.class_name:
        raise HTTPException(status_code=400, detail="Buổi học chưa được gán lớp.")

    block_reason = official_attendance_block_reason(student)
    if block_reason:
        raise HTTPException(status_code=403, detail=block_reason)

    session_enrollment_count = count_session_enrollments(db, session)
    if session_enrollment_count == 0:
        alert = create_alert(
            db,
            session_id=session_id,
            alert_type="NOT_ENROLLED",
            student_id=student.id,
            captured_img=image_path,
            confidence=confidence,
            liveness_score=liveness_score,
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            note="Session has no student enrollment list.",
        )
        return _security_alert_response(
            "not_enrolled",
            "Sinh viên không thuộc lớp học phần này",
            alert,
        )

    session_enrollment_count = validate_min_session_enrollments(db, session)
    if not _is_student_enrolled_in_session(db, student, session):
        alert = create_alert(
            db,
            session_id=session_id,
            alert_type="NOT_ENROLLED",
            student_id=student.id,
            captured_img=image_path,
            confidence=confidence,
            liveness_score=liveness_score,
            gps_lat=gps_lat,
            gps_lng=gps_lng,
            note="Recognized student is not enrolled in this session.",
        )
        return _security_alert_response(
            "not_enrolled",
            "Sinh viên không thuộc lớp học phần này",
            alert,
        )

    check_in_at = now_in_app_timezone()
    try:
        validate_checkin_window(session, check_in_at)
    except HTTPException as exc:
        detail = exc.detail if isinstance(exc.detail, dict) else {}
        if session_enrollment_count > 0 and detail.get("status") in {"not_started", "expired", "attendance_closed"}:
            alert = create_alert(
                db,
                session_id=session_id,
                alert_type="LATE_ENTRY",
                student_id=student.id,
                captured_img=image_path,
                confidence=confidence,
                liveness_score=liveness_score,
                gps_lat=gps_lat,
                gps_lng=gps_lng,
                note=detail.get("message"),
            )
            return _security_alert_response(
                detail.get("status") or "expired",
                detail.get("message") or "Lớp học đã kết thúc điểm danh",
                alert,
            )
        raise

    existing = get_session_record(db, student.id, session_id)
    gps_data = validate_gps(db, session, gps_lat=gps_lat, gps_lng=gps_lng, gps_accuracy=gps_accuracy) or {}

    if existing:
        if existing.status in {"present", "late"}:
            existing.status = "left_early"
            scan_note = "marked_left_early"
        elif existing.status == "left_early":
            existing.status = calculate_attendance_status(session, existing.check_in_at or check_in_at)
            scan_note = "restored_attendance"
        else:
            scan_note = "unchanged"

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
                liveness_score=liveness_score,
                recognition_status=recognition_status,
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
            "success": True,
            "reason": None,
            "message": f"{student.full_name} đã được ghi nhận ra về cho buổi học này.",
            "data": serialize_record(existing, student),
        }

    existing.check_out_at = now_in_app_timezone()
    existing.check_out_conf = confidence
    db.commit()
    db.refresh(existing)

    return {
        "status": "success",
        "success": True,
        "reason": None,
        "message": f"Đã ghi nhận ra về cho {student.full_name}.",
        "data": serialize_record(existing, student),
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
