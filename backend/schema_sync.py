from sqlalchemy import inspect, text


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
                IF NOT EXISTS (
                    SELECT 1 FROM pg_constraint WHERE conname = 'ck_users_role'
                ) THEN
                    ALTER TABLE users
                    ADD CONSTRAINT ck_users_role CHECK (role IN ('admin', 'teacher', 'viewer'));
                END IF;
            END $$;
            """
        )
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

            connection.execute(text("UPDATE sessions SET start_time = '07:00:00' WHERE start_time IS NULL"))
            connection.execute(text("UPDATE sessions SET end_time = '09:00:00' WHERE end_time IS NULL"))

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

        if "users" in tables:
            _sync_user_columns(connection, _get_columns(inspector, "users"))
