"""Best-effort migration from the legacy dataset schema to the normalized schema."""

from __future__ import annotations

import os
from typing import Iterable
from dotenv import load_dotenv

load_dotenv()

from sqlalchemy import create_engine, inspect, text


def _engine():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL is required")
    options = {"pool_pre_ping": True}
    if database_url.startswith("postgresql"):
        options["connect_args"] = {"sslmode": "require"}
    return create_engine(database_url, **options)


def _table_exists(inspector, table_name: str) -> bool:
    return table_name in inspector.get_table_names()


def _column_exists(inspector, table_name: str, column_name: str) -> bool:
    return _table_exists(inspector, table_name) and any(
        column["name"] == column_name for column in inspector.get_columns(table_name)
    )


def _execute(connection, sql: str) -> None:
    connection.execute(text(sql))


def _ensure_index(connection, index_name: str, table_name: str, column_name: str) -> None:
    _execute(
        connection,
        f"CREATE INDEX IF NOT EXISTS {index_name} ON {table_name} ({column_name})",
    )


def migrate_students(engine) -> None:
    inspector = inspect(engine)
    if not _table_exists(inspector, "students"):
        return

    with engine.begin() as connection:
        if _column_exists(inspector, "students", "department") and not _column_exists(inspector, "students", "dept"):
            _execute(connection, "ALTER TABLE students ADD COLUMN dept VARCHAR")
            _execute(
                connection,
                "UPDATE students SET dept = department WHERE dept IS NULL AND department IS NOT NULL",
            )
        if _column_exists(inspector, "students", "semester") and not _column_exists(inspector, "students", "sem"):
            _execute(connection, "ALTER TABLE students ADD COLUMN sem VARCHAR")
            _execute(
                connection,
                "UPDATE students SET sem = semester WHERE sem IS NULL AND semester IS NOT NULL",
            )
        if _column_exists(inspector, "students", "dept"):
            _execute(connection, "UPDATE students SET dept = COALESCE(dept, department, 'Unknown')")
        if _column_exists(inspector, "students", "sem"):
            _execute(connection, "UPDATE students SET sem = COALESCE(sem, semester, 'Unknown')")
        _ensure_index(connection, "ix_students_roll_no", "students", "roll_no")


def migrate_student_images(engine) -> None:
    inspector = inspect(engine)
    if not _table_exists(inspector, "student_images"):
        return

    with engine.begin() as connection:
        if _column_exists(inspector, "student_images", "id") and not _column_exists(inspector, "student_images", "image_id"):
            _execute(connection, "ALTER TABLE student_images RENAME COLUMN id TO image_id")
        if _column_exists(inspector, "student_images", "student_id") and not _column_exists(inspector, "student_images", "roll_no"):
            _execute(connection, "ALTER TABLE student_images ADD COLUMN roll_no VARCHAR")
            if _table_exists(inspector, "students") and _column_exists(inspector, "students", "id"):
                _execute(
                    connection,
                    """
                    UPDATE student_images
                    SET roll_no = students.roll_no
                    FROM students
                    WHERE student_images.student_id = students.id
                    """.strip(),
                )
        if _column_exists(inspector, "student_images", "student_id"):
            _execute(connection, "ALTER TABLE student_images DROP COLUMN student_id")
        _ensure_index(connection, "ix_student_images_roll_no", "student_images", "roll_no")


def migrate_sessions(engine) -> None:
    inspector = inspect(engine)
    if not _table_exists(inspector, "attendance_sessions"):
        return

    with engine.begin() as connection:
        if _column_exists(inspector, "attendance_sessions", "user_name") and not _column_exists(inspector, "attendance_sessions", "prof_name"):
            _execute(connection, "ALTER TABLE attendance_sessions RENAME COLUMN user_name TO prof_name")
        if _column_exists(inspector, "attendance_sessions", "session_start") and not _column_exists(inspector, "attendance_sessions", "start_time"):
            _execute(connection, "ALTER TABLE attendance_sessions RENAME COLUMN session_start TO start_time")
        if _column_exists(inspector, "attendance_sessions", "session_end") and not _column_exists(inspector, "attendance_sessions", "end_time"):
            _execute(connection, "ALTER TABLE attendance_sessions RENAME COLUMN session_end TO end_time")
        if not _column_exists(inspector, "attendance_sessions", "expected_students"):
            _execute(connection, "ALTER TABLE attendance_sessions ADD COLUMN expected_students INTEGER")
        if not _column_exists(inspector, "attendance_sessions", "captured_students"):
            _execute(connection, "ALTER TABLE attendance_sessions ADD COLUMN captured_students INTEGER NOT NULL DEFAULT 0")
        if _column_exists(inspector, "attendance_sessions", "total_cycles_completed"):
            _execute(
                connection,
                "UPDATE attendance_sessions SET captured_students = COALESCE(captured_students, total_cycles_completed, 0)",
            )
        if _column_exists(inspector, "attendance_sessions", "total_images_collected"):
            _execute(
                connection,
                "UPDATE attendance_sessions SET captured_students = GREATEST(COALESCE(captured_students, 0), COALESCE(total_images_collected, 0))",
            )
        if _column_exists(inspector, "attendance_sessions", "status"):
            _execute(connection, "UPDATE attendance_sessions SET status = UPPER(status)")
        if _column_exists(inspector, "attendance_sessions", "id"):
            _execute(connection, "ALTER TABLE attendance_sessions DROP COLUMN id")
        for legacy_column in ["student_id", "duration_minutes", "collection_type", "total_images_collected", "total_cycles_completed"]:
            if _column_exists(inspector, "attendance_sessions", legacy_column):
                _execute(connection, f"ALTER TABLE attendance_sessions DROP COLUMN {legacy_column}")
        _ensure_index(connection, "ix_attendance_sessions_session_id", "attendance_sessions", "session_id")
        _ensure_index(connection, "ix_attendance_sessions_course_name", "attendance_sessions", "course_name")


def migrate_captures(engine) -> None:
    inspector = inspect(engine)
    if not _table_exists(inspector, "attendance_captures"):
        return

    with engine.begin() as connection:
        if _column_exists(inspector, "attendance_captures", "capture_id") and _column_exists(inspector, "attendance_captures", "id"):
            _execute(connection, "ALTER TABLE attendance_captures DROP COLUMN capture_id")
            _execute(connection, "ALTER TABLE attendance_captures RENAME COLUMN id TO capture_id")
        elif _column_exists(inspector, "attendance_captures", "id") and not _column_exists(inspector, "attendance_captures", "capture_id"):
            _execute(connection, "ALTER TABLE attendance_captures RENAME COLUMN id TO capture_id")

        for legacy_column in ["cycle_id", "face_count", "verification_status", "image_width", "image_height", "capture_number", "device_info", "created_at"]:
            if _column_exists(inspector, "attendance_captures", legacy_column):
                _execute(connection, f"ALTER TABLE attendance_captures DROP COLUMN {legacy_column}")
        _ensure_index(connection, "ix_attendance_captures_session_id", "attendance_captures", "session_id")


def migrate_records(engine) -> None:
    with engine.begin() as connection:
        _execute(
            connection,
            """
            CREATE TABLE IF NOT EXISTS attendance_records (
                record_id BIGSERIAL PRIMARY KEY,
                session_id VARCHAR NOT NULL REFERENCES attendance_sessions (session_id) ON DELETE CASCADE,
                roll_no VARCHAR NOT NULL REFERENCES students (roll_no) ON DELETE CASCADE,
                confidence_score DOUBLE PRECISION NOT NULL,
                marked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                status VARCHAR NOT NULL DEFAULT 'PRESENT',
                CONSTRAINT uq_attendance_records_session_roll UNIQUE (session_id, roll_no),
                CONSTRAINT ck_attendance_records_status CHECK (status IN ('PRESENT', 'ABSENT', 'MANUALLY_VERIFIED')),
                CONSTRAINT ck_attendance_records_confidence_score CHECK (confidence_score >= 0 AND confidence_score <= 1)
            )
            """.strip(),
        )
        _ensure_index(connection, "ix_attendance_records_session_id", "attendance_records", "session_id")
        _ensure_index(connection, "ix_attendance_records_roll_no", "attendance_records", "roll_no")


def main() -> None:
    engine = _engine()
    migrate_students(engine)
    migrate_student_images(engine)
    migrate_sessions(engine)
    migrate_captures(engine)
    migrate_records(engine)


if __name__ == "__main__":
    main()
