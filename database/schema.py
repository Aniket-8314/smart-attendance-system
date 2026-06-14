"""Database creation and small, idempotent schema upgrades."""

from typing import Dict

from sqlalchemy import inspect, text


SESSION_COLUMNS: Dict[str, str] = {
    "collection_type": "VARCHAR NOT NULL DEFAULT 'attendance'",
    "total_cycles_completed": "INTEGER NOT NULL DEFAULT 0",
}

CAPTURE_COLUMNS: Dict[str, str] = {
    "cycle_id": "VARCHAR NOT NULL DEFAULT 'cycle_001'",
}


def _add_missing_columns(engine, table_name: str, columns: Dict[str, str]) -> None:
    inspector = inspect(engine)
    if table_name not in inspector.get_table_names():
        return

    existing = {column["name"] for column in inspector.get_columns(table_name)}
    with engine.begin() as connection:
        for name, definition in columns.items():
            if name not in existing:
                connection.execute(
                    text(f"ALTER TABLE {table_name} ADD COLUMN {name} {definition}")
                )


def _make_student_id_nullable(engine) -> None:
    """Allow instructor-only sessions that are not linked to a student."""
    inspector = inspect(engine)
    if "attendance_sessions" not in inspector.get_table_names():
        return

    student_id = next(
        (
            column
            for column in inspector.get_columns("attendance_sessions")
            if column["name"] == "student_id"
        ),
        None,
    )
    if student_id is None or student_id.get("nullable", True):
        return

    if engine.dialect.name == "postgresql":
        with engine.begin() as connection:
            connection.execute(
                text(
                    "ALTER TABLE attendance_sessions "
                    "ALTER COLUMN student_id DROP NOT NULL"
                )
            )


def initialize_database(engine, base) -> None:
    """Create missing tables and upgrade known legacy schemas in place."""
    base.metadata.create_all(bind=engine)
    _add_missing_columns(engine, "attendance_sessions", SESSION_COLUMNS)
    _add_missing_columns(engine, "attendance_captures", CAPTURE_COLUMNS)
    _make_student_id_nullable(engine)
