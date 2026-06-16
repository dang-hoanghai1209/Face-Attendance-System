from sqlalchemy import inspect, text

from models.session import DEFAULT_GPS_RADIUS_METERS


def _get_columns(inspector, table_name):
    return {column["name"] for column in inspector.get_columns(table_name)}


def _column_expr(columns, *names, default="NULL"):
    for name in names:
        if name in columns:
            return name
    return default


def _sync_attendance_columns(connection, table_name, columns):
    if "check_in_at" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN check_in_at TIMESTAMP"))
        columns.add("check_in_at")
    if "check_out_at" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN check_out_at TIMESTAMP"))
        columns.add("check_out_at")
    if "check_in_conf" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN check_in_conf FLOAT"))
        columns.add("check_in_conf")
    if "check_out_conf" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN check_out_conf FLOAT"))
        columns.add("check_out_conf")
    if "check_in_img" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN check_in_img VARCHAR(255)"))
        columns.add("check_in_img")
    if "gps_lat" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN gps_lat FLOAT"))
        columns.add("gps_lat")
    if "gps_lng" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN gps_lng FLOAT"))
        columns.add("gps_lng")
    if "gps_accuracy" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN gps_accuracy FLOAT"))
        columns.add("gps_accuracy")
    if "distance_meters" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN distance_meters FLOAT"))
        columns.add("distance_meters")
    if "liveness_passed" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN liveness_passed BOOLEAN DEFAULT FALSE"))
        columns.add("liveness_passed")
    if "scan_count" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN scan_count INTEGER DEFAULT 0 NOT NULL"))
        columns.add("scan_count")
    if "last_scan_at" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN last_scan_at TIMESTAMP"))
        columns.add("last_scan_at")
    if "note" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN note TEXT"))
        columns.add("note")
    if "created_at" not in columns:
        connection.execute(text(f"ALTER TABLE {table_name} ADD COLUMN created_at TIMESTAMP"))
        columns.add("created_at")

    if "checked_in_at" in columns:
        connection.execute(
            text(
                f"UPDATE {table_name} "
                "SET check_in_at = COALESCE(check_in_at, checked_in_at) "
                "WHERE checked_in_at IS NOT NULL"
            )
        )

    if "confidence" in columns:
        connection.execute(
            text(
                f"UPDATE {table_name} "
                "SET check_in_conf = COALESCE(check_in_conf, confidence) "
                "WHERE confidence IS NOT NULL"
            )
        )

    connection.execute(
        text(
            f"UPDATE {table_name} "
            "SET created_at = COALESCE(created_at, check_in_at, CURRENT_TIMESTAMP)"
        )
    )
    connection.execute(
        text(
            f"UPDATE {table_name} "
            "SET status = 'present' "
            "WHERE status IS NULL OR status = ''"
        )
    )
    connection.execute(text(f"UPDATE {table_name} SET scan_count = 0 WHERE scan_count IS NULL"))


def _migrate_attendance_log(connection, inspector):
    tables = set(inspector.get_table_names())
    if "attendance" not in tables or "attendance_log" not in tables:
        return

    source_columns = _get_columns(inspector, "attendance_log")
    if not {"student_id", "session_id"}.issubset(source_columns):
        return

    status_expr = _column_expr(source_columns, "status", default="'present'")
    check_in_expr = _column_expr(source_columns, "check_in_at", "checked_in_at")
    check_out_expr = _column_expr(source_columns, "check_out_at")
    check_in_conf_expr = _column_expr(source_columns, "check_in_conf", "confidence")
    check_out_conf_expr = _column_expr(source_columns, "check_out_conf")
    check_in_img_expr = _column_expr(source_columns, "check_in_img")
    note_expr = _column_expr(source_columns, "note")
    created_at_expr = _column_expr(source_columns, "created_at", "check_in_at", "checked_in_at", default="CURRENT_TIMESTAMP")
    id_order_expr = "id NULLS LAST" if "id" in source_columns else "student_id"

    connection.execute(
        text(
            f"""
            INSERT INTO attendance (
                student_id,
                session_id,
                check_in_at,
                check_out_at,
                check_in_conf,
                check_out_conf,
                check_in_img,
                status,
                note,
                created_at
            )
            SELECT DISTINCT ON (student_id, session_id)
                student_id,
                session_id,
                {check_in_expr},
                {check_out_expr},
                {check_in_conf_expr},
                {check_out_conf_expr},
                {check_in_img_expr},
                COALESCE(NULLIF({status_expr}, ''), 'present'),
                {note_expr},
                COALESCE({created_at_expr}, {check_in_expr}, CURRENT_TIMESTAMP)
            FROM attendance_log source
            WHERE student_id IS NOT NULL
              AND session_id IS NOT NULL
              AND NOT EXISTS (
                  SELECT 1
                  FROM attendance target
                  WHERE target.student_id = source.student_id
                    AND target.session_id = source.session_id
              )
            ORDER BY student_id, session_id, {created_at_expr} NULLS LAST, {id_order_expr}
            """
        )
    )


def _add_attendance_unique_constraint(connection):
    duplicate_count = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM (
                SELECT student_id, session_id
                FROM attendance
                WHERE student_id IS NOT NULL AND session_id IS NOT NULL
                GROUP BY student_id, session_id
                HAVING COUNT(*) > 1
            ) AS duplicates
            """
        )
    ).scalar()

    if duplicate_count:
        return

    connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_attendance_student_session'
                ) THEN
                    ALTER TABLE attendance
                    ADD CONSTRAINT uq_attendance_student_session UNIQUE (student_id, session_id);
                END IF;
            END $$;
            """
        )
    )


def _sync_recognition_attempt_columns(connection, columns):
    if "session_id" not in columns:
        connection.execute(text("ALTER TABLE recognition_attempts ADD COLUMN session_id INTEGER"))
    if "predicted_student_id" not in columns:
        connection.execute(text("ALTER TABLE recognition_attempts ADD COLUMN predicted_student_id INTEGER"))
    if "predicted_student_code" not in columns:
        connection.execute(text("ALTER TABLE recognition_attempts ADD COLUMN predicted_student_code VARCHAR(8)"))
    if "confidence" not in columns:
        connection.execute(text("ALTER TABLE recognition_attempts ADD COLUMN confidence FLOAT"))
    if "status" not in columns:
        connection.execute(text("ALTER TABLE recognition_attempts ADD COLUMN status VARCHAR(20)"))
    if "image_path" not in columns:
        connection.execute(text("ALTER TABLE recognition_attempts ADD COLUMN image_path VARCHAR(255)"))
    if "message" not in columns:
        connection.execute(text("ALTER TABLE recognition_attempts ADD COLUMN message TEXT"))
    if "created_at" not in columns:
        connection.execute(text("ALTER TABLE recognition_attempts ADD COLUMN created_at TIMESTAMP"))

    connection.execute(
        text("UPDATE recognition_attempts SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL")
    )
    connection.execute(
        text("UPDATE recognition_attempts SET status = 'unknown' WHERE status IS NULL OR status = ''")
    )


def _sync_attendance_scan_columns(connection, columns):
    if "attendance_id" not in columns:
        connection.execute(text("ALTER TABLE attendance_scans ADD COLUMN attendance_id INTEGER"))
        columns.add("attendance_id")
    if "scanned_at" not in columns:
        connection.execute(text("ALTER TABLE attendance_scans ADD COLUMN scanned_at TIMESTAMP"))
        columns.add("scanned_at")
    if "confidence" not in columns:
        connection.execute(text("ALTER TABLE attendance_scans ADD COLUMN confidence FLOAT"))
        columns.add("confidence")
    if "gps_lat" not in columns:
        connection.execute(text("ALTER TABLE attendance_scans ADD COLUMN gps_lat FLOAT"))
        columns.add("gps_lat")
    if "gps_lng" not in columns:
        connection.execute(text("ALTER TABLE attendance_scans ADD COLUMN gps_lng FLOAT"))
        columns.add("gps_lng")
    if "liveness_passed" not in columns:
        connection.execute(text("ALTER TABLE attendance_scans ADD COLUMN liveness_passed BOOLEAN"))
        columns.add("liveness_passed")
    if "scan_index" not in columns:
        connection.execute(text("ALTER TABLE attendance_scans ADD COLUMN scan_index INTEGER"))
        columns.add("scan_index")
    if "note" not in columns:
        connection.execute(text("ALTER TABLE attendance_scans ADD COLUMN note TEXT"))
        columns.add("note")

    connection.execute(text("UPDATE attendance_scans SET scanned_at = CURRENT_TIMESTAMP WHERE scanned_at IS NULL"))


def _sync_user_columns(connection, columns):
    if "username" not in columns:
        connection.execute(text("ALTER TABLE users ADD COLUMN username VARCHAR(80)"))
        columns.add("username")
    if "password_hash" not in columns:
        connection.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)"))
        columns.add("password_hash")
    if "full_name" not in columns:
        connection.execute(text("ALTER TABLE users ADD COLUMN full_name VARCHAR(120)"))
        columns.add("full_name")
    if "role" not in columns:
        connection.execute(text("ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'teacher' NOT NULL"))
        columns.add("role")
    if "is_active" not in columns:
        connection.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE NOT NULL"))
        columns.add("is_active")
    if "created_at" not in columns:
        connection.execute(text("ALTER TABLE users ADD COLUMN created_at TIMESTAMP"))
        columns.add("created_at")

    connection.execute(text("UPDATE users SET role = 'teacher' WHERE role IS NULL OR role = ''"))
    connection.execute(text("UPDATE users SET is_active = TRUE WHERE is_active IS NULL"))
    connection.execute(text("UPDATE users SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
    connection.execute(
        text(
            """
            DO $$
            BEGIN
                ALTER TABLE users DROP CONSTRAINT IF EXISTS ck_users_role;
                ALTER TABLE users
                ADD CONSTRAINT ck_users_role CHECK (role IN ('admin', 'teacher', 'lecturer', 'student', 'viewer'));
            END $$;
            """
        )
    )


def _sync_enrollment_columns(connection, columns):
    if "session_id" not in columns:
        connection.execute(text("ALTER TABLE enrollments ADD COLUMN session_id INTEGER"))
        columns.add("session_id")
    if "enrolled_at" not in columns:
        connection.execute(text("ALTER TABLE enrollments ADD COLUMN enrolled_at TIMESTAMP"))
        columns.add("enrolled_at")
    if "note" not in columns:
        connection.execute(text("ALTER TABLE enrollments ADD COLUMN note TEXT"))
        columns.add("note")
    if "course_section_id" not in columns:
        connection.execute(text("ALTER TABLE enrollments ADD COLUMN course_section_id INTEGER"))
        columns.add("course_section_id")
    if "status" not in columns:
        connection.execute(text("ALTER TABLE enrollments ADD COLUMN status VARCHAR(20) DEFAULT 'active' NOT NULL"))
        columns.add("status")
    if "created_at" not in columns:
        connection.execute(text("ALTER TABLE enrollments ADD COLUMN created_at TIMESTAMP"))
        columns.add("created_at")
    if "updated_at" not in columns:
        connection.execute(text("ALTER TABLE enrollments ADD COLUMN updated_at TIMESTAMP"))
        columns.add("updated_at")

    connection.execute(text("UPDATE enrollments SET enrolled_at = CURRENT_TIMESTAMP WHERE enrolled_at IS NULL"))
    connection.execute(text("UPDATE enrollments SET status = 'active' WHERE status IS NULL OR status = ''"))
    connection.execute(text("UPDATE enrollments SET created_at = COALESCE(created_at, enrolled_at, CURRENT_TIMESTAMP)"))
    connection.execute(text("UPDATE enrollments SET updated_at = COALESCE(updated_at, created_at, CURRENT_TIMESTAMP)"))
    connection.execute(text("CREATE INDEX IF NOT EXISTS ix_enrollments_session_id ON enrollments (session_id)"))


def _add_enrollment_session_unique_constraint(connection):
    if connection.dialect.name != "postgresql":
        return

    duplicate_count = connection.execute(
        text(
            """
            SELECT COUNT(*)
            FROM (
                SELECT session_id, student_id
                FROM enrollments
                WHERE session_id IS NOT NULL AND student_id IS NOT NULL
                GROUP BY session_id, student_id
                HAVING COUNT(*) > 1
            ) AS duplicates
            """
        )
    ).scalar()

    if duplicate_count:
        return

    connection.execute(
        text(
            """
            DO $$
            BEGIN
                IF NOT EXISTS (
                    SELECT 1
                    FROM pg_constraint
                    WHERE conname = 'uq_enrollments_session_student'
                ) THEN
                    ALTER TABLE enrollments
                    ADD CONSTRAINT uq_enrollments_session_student UNIQUE (session_id, student_id);
                END IF;
            END $$;
            """
        )
    )


def _sync_security_alert_columns(connection, columns):
    if "session_id" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN session_id INTEGER"))
        columns.add("session_id")
    if "alert_type" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN alert_type VARCHAR(20)"))
        columns.add("alert_type")
    if "student_id" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN student_id INTEGER"))
        columns.add("student_id")
    if "captured_img" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN captured_img VARCHAR(255)"))
        columns.add("captured_img")
    if "confidence" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN confidence FLOAT"))
        columns.add("confidence")
    if "liveness_score" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN liveness_score FLOAT"))
        columns.add("liveness_score")
    if "gps_lat" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN gps_lat FLOAT"))
        columns.add("gps_lat")
    if "gps_lng" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN gps_lng FLOAT"))
        columns.add("gps_lng")
    if "dismissed" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN dismissed BOOLEAN DEFAULT FALSE NOT NULL"))
        columns.add("dismissed")
    if "dismissed_by" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN dismissed_by VARCHAR(80)"))
        columns.add("dismissed_by")
    if "dismissed_at" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN dismissed_at TIMESTAMP"))
        columns.add("dismissed_at")
    if "note" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN note TEXT"))
        columns.add("note")
    if "created_at" not in columns:
        connection.execute(text("ALTER TABLE security_alerts ADD COLUMN created_at TIMESTAMP"))
        columns.add("created_at")

    connection.execute(text("UPDATE security_alerts SET dismissed = FALSE WHERE dismissed IS NULL"))
    connection.execute(text("UPDATE security_alerts SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
    connection.execute(
        text("CREATE INDEX IF NOT EXISTS ix_security_alerts_session_dismissed ON security_alerts (session_id, dismissed)")
    )


def sync_schema(engine):
    inspector = inspect(engine)
    tables = set(inspector.get_table_names())

    with engine.begin() as connection:
        if "students" in tables:
            columns = _get_columns(inspector, "students")

            if "face_status" not in columns:
                connection.execute(
                    text("ALTER TABLE students ADD COLUMN face_status VARCHAR(20) DEFAULT 'unregistered'")
                )
                columns.add("face_status")
            if "data_source" not in columns:
                connection.execute(
                    text("ALTER TABLE students ADD COLUMN data_source VARCHAR(20) DEFAULT 'real' NOT NULL")
                )
                columns.add("data_source")
            if "registration_method" not in columns:
                connection.execute(text("ALTER TABLE students ADD COLUMN registration_method VARCHAR(20)"))
                columns.add("registration_method")
            if "is_demo" not in columns:
                connection.execute(
                    text("ALTER TABLE students ADD COLUMN is_demo BOOLEAN DEFAULT FALSE NOT NULL")
                )
                columns.add("is_demo")
            if "avatar_path" not in columns:
                connection.execute(text("ALTER TABLE students ADD COLUMN avatar_path VARCHAR(255)"))
                columns.add("avatar_path")

            connection.execute(
                text("UPDATE students SET face_status = 'unregistered' WHERE face_status IS NULL OR face_status = ''")
            )
            connection.execute(
                text("UPDATE students SET data_source = 'real' WHERE data_source IS NULL OR data_source = ''")
            )
            connection.execute(
                text("UPDATE students SET is_demo = FALSE WHERE is_demo IS NULL")
            )
            connection.execute(
                text(
                    """
                    UPDATE students
                    SET data_source = 'lfw',
                        is_demo = TRUE,
                        registration_method = COALESCE(NULLIF(registration_method, ''), 'lfw_import')
                    WHERE UPPER(COALESCE(class_name, '')) LIKE '%LFW%'
                       OR LOWER(COALESCE(data_source, '')) IN ('lfw', 'evaluation', 'kaggle')
                       OR LOWER(COALESCE(registration_method, '')) IN ('lfw_import', 'evaluation_import', 'lfw_folder_mean')
                    """
                )
            )
            connection.execute(
                text(
                    """
                    UPDATE students
                    SET data_source = 'demo',
                        is_demo = TRUE,
                        registration_method = COALESCE(NULLIF(registration_method, ''), 'demo_seed')
                    WHERE data_source = 'real'
                      AND (
                          LOWER(COALESCE(full_name, '')) LIKE '%demo%'
                          OR LOWER(COALESCE(full_name, '')) LIKE '%mvp%'
                          OR LOWER(COALESCE(registration_method, '')) LIKE '%demo%'
                      )
                    """
                )
            )

            if "face_embeddings" in tables:
                connection.execute(
                    text(
                        "UPDATE students "
                        "SET face_status = 'registered' "
                        "WHERE id IN (SELECT DISTINCT student_id FROM face_embeddings)"
                    )
                )

        if "sessions" in tables:
            columns = _get_columns(inspector, "sessions")

            if "start_time" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN start_time TIME"))
            if "end_time" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN end_time TIME"))
            if "created_at" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN created_at TIMESTAMP"))
                connection.execute(text("UPDATE sessions SET created_at = CURRENT_TIMESTAMP WHERE created_at IS NULL"))
            if "section_id" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN section_id INTEGER"))
            if "classroom_id" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN classroom_id INTEGER"))
            if "note" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN note TEXT"))
            if "latitude" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN latitude FLOAT"))
            if "longitude" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN longitude FLOAT"))
            if "radius_meters" not in columns:
                connection.execute(
                    text(f"ALTER TABLE sessions ADD COLUMN radius_meters INTEGER DEFAULT {DEFAULT_GPS_RADIUS_METERS}")
                )
            if "room_name" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN room_name VARCHAR(100)"))
            if "session_number" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN session_number INTEGER"))
            if "section_group" not in columns:
                connection.execute(text("ALTER TABLE sessions ADD COLUMN section_group VARCHAR(30)"))
                columns.add("section_group")

            connection.execute(text("UPDATE sessions SET start_time = '07:00:00' WHERE start_time IS NULL"))
            connection.execute(text("UPDATE sessions SET end_time = '09:00:00' WHERE end_time IS NULL"))
            connection.execute(
                text(f"UPDATE sessions SET radius_meters = {DEFAULT_GPS_RADIUS_METERS} WHERE radius_meters IS NULL")
            )

        if "course_sections" in tables:
            columns = _get_columns(inspector, "course_sections")
            if "class_name" not in columns:
                connection.execute(text("ALTER TABLE course_sections ADD COLUMN class_name VARCHAR(50)"))
                columns.add("class_name")
                connection.execute(text(
                    "UPDATE course_sections "
                    "SET class_name = REPLACE(REPLACE(section_code, '-', ''), ' ', '') "
                    "WHERE (class_name IS NULL OR class_name = '') "
                    "  AND REPLACE(REPLACE(section_code, '-', ''), ' ', '') IN "
                    "('63TTQL', '63HTTT', '63CNTT', '63LFW', '64TTQL', '64HTTT', '64CNTT', '64LFW')"
                ))
            if "section_group" not in columns:
                connection.execute(text("ALTER TABLE course_sections ADD COLUMN section_group VARCHAR(30)"))
                columns.add("section_group")

        if "attendance" in tables:
            _sync_attendance_columns(connection, "attendance", _get_columns(inspector, "attendance"))

        if "attendance_log" in tables:
            _sync_attendance_columns(connection, "attendance_log", _get_columns(inspector, "attendance_log"))
            _migrate_attendance_log(connection, inspector)

        if "attendance" in tables:
            _add_attendance_unique_constraint(connection)

        if "recognition_attempts" in tables:
            _sync_recognition_attempt_columns(
                connection,
                _get_columns(inspector, "recognition_attempts"),
            )

        if "attendance_scans" in tables:
            _sync_attendance_scan_columns(connection, _get_columns(inspector, "attendance_scans"))

        if "users" in tables:
            _sync_user_columns(connection, _get_columns(inspector, "users"))

        if "enrollments" in tables:
            _sync_enrollment_columns(connection, _get_columns(inspector, "enrollments"))
            _add_enrollment_session_unique_constraint(connection)

        if "security_alerts" in tables:
            _sync_security_alert_columns(connection, _get_columns(inspector, "security_alerts"))
