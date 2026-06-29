from sqlalchemy import CheckConstraint, Column, DateTime, Float, ForeignKey, Index, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.db import Base


class Student(Base):
    __tablename__ = "students"

    roll_no = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    dept = Column(String, nullable=False)
    sem = Column(String, nullable=False)

    images = relationship(
        "StudentImage",
        back_populates="student",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_students_roll_no", "roll_no"),
    )


class StudentImage(Base):
    __tablename__ = "student_images"

    image_id = Column(Integer, primary_key=True, autoincrement=True)
    roll_no = Column(String, ForeignKey("students.roll_no", ondelete="CASCADE"), nullable=False)
    image_path = Column(String, nullable=False)
    uploaded_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    student = relationship("Student", back_populates="images")

    __table_args__ = (
        Index("ix_student_images_roll_no", "roll_no"),
    )


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    session_id = Column(String, primary_key=True)
    prof_name = Column(String, nullable=False)
    course_name = Column(String, nullable=False)
    start_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)
    expected_students = Column(Integer, nullable=True)
    captured_students = Column(Integer, nullable=False, default=0)
    status = Column(String, nullable=False, default="ACTIVE")

    captures = relationship(
        "AttendanceCapture",
        back_populates="session",
        cascade="all, delete-orphan",
    )
    records = relationship(
        "AttendanceRecord",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    __table_args__ = (
        Index("ix_attendance_sessions_session_id", "session_id"),
        Index("ix_attendance_sessions_course_name", "course_name"),
        CheckConstraint("status IN ('ACTIVE', 'CLOSED')", name="ck_attendance_sessions_status"),
    )


class AttendanceCapture(Base):
    __tablename__ = "attendance_captures"

    capture_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String,
        ForeignKey("attendance_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    image_path = Column(String, nullable=False)
    capture_time = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    session = relationship("AttendanceSession", back_populates="captures")

    __table_args__ = (
        Index("ix_attendance_captures_session_id", "session_id"),
    )


class AttendanceRecord(Base):
    __tablename__ = "attendance_records"

    record_id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(
        String,
        ForeignKey("attendance_sessions.session_id", ondelete="CASCADE"),
        nullable=False,
    )
    roll_no = Column(
        String,
        ForeignKey("students.roll_no", ondelete="CASCADE"),
        nullable=False,
    )
    confidence_score = Column(Float, nullable=False)
    marked_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    status = Column(String, nullable=False, default="PRESENT")

    session = relationship("AttendanceSession", back_populates="records")
    student = relationship("Student")

    __table_args__ = (
        Index("ix_attendance_records_session_id", "session_id"),
        Index("ix_attendance_records_roll_no", "roll_no"),
        UniqueConstraint("session_id", "roll_no", name="uq_attendance_records_session_roll"),
        CheckConstraint(
            "status IN ('PRESENT', 'ABSENT', 'MANUALLY_VERIFIED')",
            name="ck_attendance_records_status",
        ),
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="ck_attendance_records_confidence_score",
        ),
    )
