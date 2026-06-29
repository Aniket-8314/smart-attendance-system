"""Database bootstrap helpers for the normalized schema."""

from sqlalchemy import text


def initialize_database(engine, base) -> None:
    """Create any missing tables for the current ORM metadata."""
    base.metadata.create_all(bind=engine)


def run_sql(engine, sql: str) -> None:
    with engine.begin() as connection:
        connection.execute(text(sql))
