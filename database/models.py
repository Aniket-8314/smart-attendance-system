import uuid

from sqlalchemy import Column, DateTime, ForeignKey, Integer, LargeBinary, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from database.db import Base


class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True)
    roll_no = Column(String, unique=True, nullable=False)
    name = Column(String, nullable=False)
    department = Column(String, nullable=False)
    semester = Column(String, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    attendance_sessions = relationship(
        "AttendanceSession",
        back_populates="student",
        cascade="all, delete-orphan",
    )


class AttendanceSession(Base):
    __tablename__ = "attendance_sessions"

    id = Column(Integer, primary_key=True)
    session_id = Column(
        String,
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    student_id = Column(Integer, ForeignKey("students.id"), nullable=True)
    user_name = Column(String, nullable=False)
    session_start = Column(DateTime(timezone=True), server_default=func.now())
    session_end = Column(DateTime(timezone=True), nullable=True)
    duration_minutes = Column(Integer, nullable=False)
    status = Column(String, nullable=False, default="active")
    total_images_collected = Column(Integer, nullable=False, default=0)
    total_cycles_completed = Column(Integer, nullable=False, default=0)
    collection_type = Column(String, nullable=False, default="attendance")
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    student = relationship("Student", back_populates="attendance_sessions")
    captures = relationship(
        "AttendanceCapture",
        back_populates="session",
        cascade="all, delete-orphan",
    )

    @property
    def instructor_name(self) -> str:
        return self.user_name


class AttendanceCapture(Base):
    __tablename__ = "attendance_captures"

    id = Column(Integer, primary_key=True)
    capture_id = Column(
        String,
        unique=True,
        nullable=False,
        default=lambda: str(uuid.uuid4()),
    )
    session_id = Column(
        String,
        ForeignKey("attendance_sessions.session_id"),
        nullable=False,
    )
    cycle_id = Column(String, nullable=False, default="cycle_001")
    image_path = Column(String, nullable=False)
    capture_time = Column(DateTime(timezone=True), server_default=func.now())
    face_count = Column(Integer, nullable=False, default=0)
    verification_status = Column(String, nullable=False, default="pending")
    image_width = Column(Integer, nullable=True)
    image_height = Column(Integer, nullable=True)
    capture_number = Column(Integer, nullable=False)
    device_info = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    session = relationship("AttendanceSession", back_populates="captures")
    image_data = relationship(
        "AttendanceCaptureImage",
        back_populates="capture",
        cascade="all, delete-orphan",
        uselist=False,
    )

    @property
    def capture_sequence(self) -> int:
        return self.capture_number


class AttendanceCaptureImage(Base):
    __tablename__ = "attendance_capture_images"

    id = Column(Integer, primary_key=True)
    capture_id = Column(
        Integer,
        ForeignKey("attendance_captures.id"),
        unique=True,
        nullable=False,
    )
    session_id = Column(String, nullable=False, index=True)
    cycle_id = Column(String, nullable=False, index=True)
    capture_number = Column(Integer, nullable=False)
    file_name = Column(String, nullable=False)
    content_type = Column(String, nullable=False, default="image/jpeg")
    image_bytes = Column(LargeBinary, nullable=False)
    byte_size = Column(Integer, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    capture = relationship("AttendanceCapture", back_populates="image_data")
