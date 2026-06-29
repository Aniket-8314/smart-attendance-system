"""Attendance persistence and storage workflows."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Iterable, List, Optional, Sequence

import cv2
import numpy as np
from sqlalchemy import distinct, func

from backend.storage_service import StorageService
from database.db import Base, SessionLocal, engine
from database.models import AttendanceCapture, AttendanceRecord, AttendanceSession, Student, StudentImage
from database.schema import initialize_database

logger = logging.getLogger(__name__)

TARGET_IMAGES = 20


def encode_frame_as_jpeg(frame: np.ndarray) -> bytes:
    success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not success:
        raise OSError("Failed to encode image as JPEG")
    return encoded.tobytes()


class AttendanceService:
    def __init__(self, storage: Optional[StorageService] = None):
        initialize_database(engine, Base)
        self.storage = storage or StorageService()

    @staticmethod
    def _ensure_confidence(confidence_score: float) -> None:
        if confidence_score < 0 or confidence_score > 1:
            raise ValueError("confidence_score must be between 0 and 1")

    @staticmethod
    def _ensure_status(status: str, allowed: Iterable[str]) -> None:
        if status not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}")

    def create_or_update_student(self, roll_no: str, name: str, dept: str, sem: str) -> Student:
        roll_no = roll_no.strip()
        name = name.strip()
        dept = dept.strip()
        sem = sem.strip()
        if not roll_no:
            raise ValueError("roll_no is required")
        if not name:
            raise ValueError("name is required")
        if not dept:
            raise ValueError("dept is required")
        if not sem:
            raise ValueError("sem is required")

        with SessionLocal() as db:
            student = db.get(Student, roll_no)
            if student is None:
                student = Student(roll_no=roll_no, name=name, dept=dept, sem=sem)
                db.add(student)
            else:
                student.name = name
                student.dept = dept
                student.sem = sem
            db.commit()
            db.refresh(student)
            return student

    def list_students(self) -> List[Student]:
        with SessionLocal() as db:
            return db.query(Student).order_by(Student.roll_no).all()

    def get_student(self, roll_no: str) -> Optional[Student]:
        with SessionLocal() as db:
            return db.get(Student, roll_no)

    def add_student_image(
        self,
        roll_no: str,
        image_bytes: bytes,
        content_type: str = "image/jpeg",
        filename: Optional[str] = None,
    ) -> StudentImage:
        if not image_bytes:
            raise ValueError("image_bytes cannot be empty")
        if self.get_student(roll_no) is None:
            raise ValueError("roll_no must exist before image insertion")

        with SessionLocal() as db:
            student = db.get(Student, roll_no)
            if student is None:
                raise ValueError("roll_no must exist before image insertion")
            image_path = self.storage.upload_student_image(
                roll_no=roll_no,
                image_bytes=image_bytes,
                content_type=content_type,
                filename=filename,
            )
            student_image = StudentImage(
                roll_no=roll_no,
                image_path=image_path,
            )
            db.add(student_image)
            db.commit()
            db.refresh(student_image)
            return student_image

    def list_student_images(self, roll_no: Optional[str] = None) -> List[StudentImage]:
        with SessionLocal() as db:
            query = db.query(StudentImage).order_by(StudentImage.uploaded_at.desc())
            if roll_no:
                query = query.filter(StudentImage.roll_no == roll_no)
            return query.all()

    def create_session(
        self,
        prof_name: str,
        course_name: str,
        expected_students: Optional[int] = None,
    ) -> AttendanceSession:
        prof_name = prof_name.strip()
        course_name = course_name.strip()
        if not prof_name:
            raise ValueError("prof_name is required")
        if not course_name:
            raise ValueError("course_name is required")
        if expected_students is not None and expected_students < 0:
            raise ValueError("expected_students must be non-negative")

        with SessionLocal() as db:
            session = AttendanceSession(
                session_id=str(uuid.uuid4()),
                prof_name=prof_name,
                course_name=course_name,
                expected_students=expected_students,
                captured_students=0,
                status="ACTIVE",
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info("Session started: %s", session.session_id)
            return session

    def get_session(self, session_id: str) -> Optional[AttendanceSession]:
        with SessionLocal() as db:
            return db.get(AttendanceSession, session_id)

    def list_sessions(self) -> List[AttendanceSession]:
        with SessionLocal() as db:
            return db.query(AttendanceSession).order_by(AttendanceSession.start_time.desc()).all()

    def close_session(self, session_id: str, captured_students: Optional[int] = None) -> Optional[AttendanceSession]:
        with SessionLocal() as db:
            session = db.get(AttendanceSession, session_id)
            if session is None:
                return None
            if session.status != "CLOSED":
                session.end_time = datetime.now(timezone.utc)
                session.status = "CLOSED"
                
                # FIXED: Preserve manual loop counter state instead of running automatic SQL database overrides
                if captured_students is not None:
                    session.captured_students = captured_students
                
                db.commit()
                db.refresh(session)
            return session

    def add_capture(
        self,
        session_id: str,
        image_bytes: bytes,
        capture_time: Optional[datetime] = None,
        filename: Optional[str] = None,
        content_type: str = "image/jpeg",
    ) -> AttendanceCapture:
        if not image_bytes:
            raise ValueError("image_bytes cannot be empty")

        with SessionLocal() as db:
            session = db.get(AttendanceSession, session_id)
            if session is None:
                raise ValueError("session_id must exist before capture insertion")
            image_path = self.storage.upload_attendance_capture(
                session_id=session_id,
                image_bytes=image_bytes,
                content_type=content_type,
                filename=filename,
            )
            capture = AttendanceCapture(
                session_id=session_id,
                image_path=image_path,
                capture_time=capture_time or datetime.now(timezone.utc),
            )
            db.add(capture)
            db.commit()
            db.refresh(capture)
            return capture

    def list_session_captures(self, session_id: str) -> List[AttendanceCapture]:
        with SessionLocal() as db:
            return (
                db.query(AttendanceCapture)
                .filter(AttendanceCapture.session_id == session_id)
                .order_by(AttendanceCapture.capture_time.desc())
                .all()
            )

    def add_attendance_record(
        self,
        session_id: str,
        roll_no: str,
        confidence_score: float,
        status: str = "PRESENT",
        marked_at: Optional[datetime] = None,
    ) -> AttendanceRecord:
        self._ensure_confidence(confidence_score)
        self._ensure_status(status, {"PRESENT", "ABSENT", "MANUALLY_VERIFIED"})

        with SessionLocal() as db:
            session = db.get(AttendanceSession, session_id)
            if session is None:
                raise ValueError("session_id must exist before attendance record insertion")
            student = db.get(Student, roll_no)
            if student is None:
                raise ValueError("roll_no must exist before attendance record insertion")

            existing = (
                db.query(AttendanceRecord)
                .filter(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.roll_no == roll_no,
                )
                .first()
            )
            if existing is not None:
                return existing

            record = AttendanceRecord(
                session_id=session_id,
                roll_no=roll_no,
                confidence_score=confidence_score,
                marked_at=marked_at or datetime.now(timezone.utc),
                status=status,
            )
            db.add(record)
            db.commit()
            db.refresh(record)
            return record

    def bulk_add_attendance_records(
        self,
        session_id: str,
        records: Sequence[Dict[str, object]],
    ) -> List[AttendanceRecord]:
        saved: List[AttendanceRecord] = []
        for record in records:
            saved.append(
                self.add_attendance_record(
                    session_id=session_id,
                    roll_no=str(record["roll_no"]),
                    confidence_score=float(record["confidence_score"]),
                    status=str(record.get("status", "PRESENT")),
                    marked_at=record.get("marked_at"),
                )
            )
        return saved

    def list_attendance_records(self, session_id: Optional[str] = None) -> List[AttendanceRecord]:
        with SessionLocal() as db:
            query = db.query(AttendanceRecord).order_by(AttendanceRecord.marked_at.desc())
            if session_id:
                query = query.filter(AttendanceRecord.session_id == session_id)
            return query.all()

    def get_session_statistics(self, session_id: str) -> Dict[str, object]:
        with SessionLocal() as db:
            session = db.get(AttendanceSession, session_id)
            if session is None:
                return {}

            capture_count = (
                db.query(func.count(AttendanceCapture.capture_id))
                .filter(AttendanceCapture.session_id == session_id)
                .scalar()
                or 0
            )
            record_count = (
                db.query(func.count(AttendanceRecord.record_id))
                .filter(AttendanceRecord.session_id == session_id)
                .scalar()
                or 0
            )
            present_count = (
                db.query(func.count(AttendanceRecord.record_id))
                .filter(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.status == "PRESENT",
                )
                .scalar()
                or 0
            )
            manually_verified_count = (
                db.query(func.count(AttendanceRecord.record_id))
                .filter(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.status == "MANUALLY_VERIFIED",
                )
                .scalar()
                or 0
            )
            absent_count = (
                db.query(func.count(AttendanceRecord.record_id))
                .filter(
                    AttendanceRecord.session_id == session_id,
                    AttendanceRecord.status == "ABSENT",
                )
                .scalar()
                or 0
            )

            return {
                "session_id": session.session_id,
                "prof_name": session.prof_name,
                "course_name": session.course_name,
                "status": session.status,
                "start_time": session.start_time,
                "end_time": session.end_time,
                "expected_students": session.expected_students,
                "captured_students": session.captured_students,
                "capture_count": capture_count,
                "record_count": record_count,
                "present_count": present_count,
                "manually_verified_count": manually_verified_count,
                "absent_count": absent_count,
            }

    def get_student_image_urls(self, roll_no: str) -> List[str]:
        images = self.list_student_images(roll_no)
        return [
            self.storage.get_public_url("student-images", image.image_path)
            for image in images
        ]

    def get_session_capture_urls(self, session_id: str) -> List[str]:
        captures = self.list_session_captures(session_id)
        return [
            self.storage.get_public_url("attendance-sessions", capture.image_path)
            for capture in captures
        ]
    
    def update_session_loop_counter(self, session_id: str, loop_count: int) -> None:
        """Directly updates the 'captured_students' database column to act as a counter."""
        with SessionLocal() as db:
            session_record = db.query(AttendanceSession).filter(
                AttendanceSession.session_id == session_id
            ).first()
            
            if session_record:
                session_record.captured_students = loop_count
                db.commit()

    def delete_student_images(self, roll_no: str) -> int:
        """
        Deletes all reference images associated with a student from 
        both Supabase storage buckets and database tracking tables cleanly.
        """
        deleted_count = 0
        with SessionLocal() as db:
            # 1. Fetch all matching metadata records for the student
            existing_images = db.query(StudentImage).filter(StudentImage.roll_no == roll_no).all()
            
            if existing_images:
                # Extract the file paths to compile a deletion batch array
                file_paths_to_purge = [img.image_path for img in existing_images]
                
                try:
                    # 2. Check how your StorageService references the Supabase Client
                    if hasattr(self.storage, 'supabase'):
                        self.storage.supabase.storage.from_("student-images").remove(file_paths_to_purge)
                    elif hasattr(self.storage, 'client'):
                        self.storage.client.storage.from_("student-images").remove(file_paths_to_purge)
                    else:
                        # Fallback direct call if your service wraps the removal internally
                        logger.warning("Could not automatically locate the Supabase Client reference variable.")
                except Exception as storage_err:
                    logger.error(f"Supabase Storage Cloud Bucket API could not purge files: {storage_err}")

                # 3. Remove tracking records from local database architecture 
                for img in existing_images:
                    try:
                        db.delete(img)
                        deleted_count += 1
                    except Exception as db_err:
                        logger.error(f"Failed to clear database metadata row {img.image_path}: {db_err}")
                
                db.commit()
                
        return deleted_count