"""Database operations for attendance dataset collection sessions."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Sequence, Tuple

import cv2
import numpy as np
from sqlalchemy import func

from backend.storage_service import StorageService
from database.db import SessionLocal, engine
from database.models import (
    AttendanceCapture,
    AttendanceCaptureImage,
    AttendanceSession,
    Base,
    Student,
)
from database.schema import initialize_database

logger = logging.getLogger(__name__)

TARGET_IMAGES = 20


def encode_frame_as_jpeg(frame: np.ndarray) -> Tuple[bytes, int, int]:
    success, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not success:
        raise OSError("Failed to encode attendance image as JPEG")
    height, width = frame.shape[:2]
    return encoded.tobytes(), width, height


class AttendanceService:
    def __init__(self, storage: Optional[StorageService] = None):
        initialize_database(engine, Base)
        self.storage = storage or StorageService()

    def create_session(
        self,
        user_name: str,
        duration_minutes: int,
        student_id: Optional[int] = None,
        collection_type: str = "attendance",
    ) -> AttendanceSession:
        instructor = user_name.strip()
        if not instructor:
            raise ValueError("Instructor name is required")
        if duration_minutes <= 0:
            raise ValueError("Session duration must be positive")

        with SessionLocal() as db:
            session = AttendanceSession(
                session_id=str(uuid.uuid4()),
                student_id=student_id,
                user_name=instructor,
                duration_minutes=duration_minutes,
                status="active",
                collection_type=collection_type,
            )
            db.add(session)
            db.commit()
            db.refresh(session)
            logger.info("Session Started: %s", session.session_id)
            return session

    def get_session(self, session_id: str) -> Optional[AttendanceSession]:
        with SessionLocal() as db:
            return db.query(AttendanceSession).filter_by(session_id=session_id).first()

    def end_session(self, session_id: str, status: str = "completed") -> Optional[AttendanceSession]:
        with SessionLocal() as db:
            session = db.query(AttendanceSession).filter_by(session_id=session_id).first()
            if session is None:
                return None
            if session.status == "active":
                session.session_end = datetime.now(timezone.utc)
                session.status = status
                db.commit()
                db.refresh(session)
                logger.info("Session Ended: %s (%s)", session_id, status)
            return session

    def generate_student_id(self, session_id: str) -> str:
        with SessionLocal() as db:
            session = db.query(AttendanceSession).filter_by(session_id=session_id).first()
            if session is None:
                raise ValueError("Attendance session not found")
            return f"STD_{session.total_cycles_completed + 1:06d}"

    def save_student_dataset(
        self,
        session_id: str,
        frames: Sequence[np.ndarray],
        capture_times: Sequence[datetime],
        device_info: str = "Browser webcam",
    ) -> Tuple[str, List[AttendanceCapture]]:
        if len(frames) != TARGET_IMAGES or len(capture_times) != TARGET_IMAGES:
            raise ValueError(f"Exactly {TARGET_IMAGES} images are required before saving")

        student_id = self.generate_student_id(session_id)
        logger.info("Student Dataset Started: %s", student_id)
        logger.info("Student ID Generated: %s", student_id)

        encoded_images = [
            (sequence, *encode_frame_as_jpeg(frame))
            for sequence, frame in enumerate(frames, start=1)
        ]

        try:
            with SessionLocal() as db:
                session = (
                    db.query(AttendanceSession)
                    .filter_by(session_id=session_id, status="active")
                    .with_for_update()
                    .first()
                )
                if session is None:
                    raise ValueError("Attendance session is no longer active")

                student = Student(
                    roll_no=f"{session_id[:8]}-{student_id}",
                    name=student_id,
                    department="Attendance Collection",
                    semester="Session",
                )
                db.add(student)
                db.flush()

                captures = []
                for (sequence, image_bytes, width, height), captured_at in zip(
                    encoded_images,
                    capture_times,
                ):
                    filename = f"image_{sequence:03d}.jpg"
                    image_path = f"db://attendance_capture_images/{session_id}/{student_id}/{filename}"
                    capture = AttendanceCapture(
                        session_id=session_id,
                        cycle_id=student_id,
                        image_path=image_path,
                        capture_time=captured_at,
                        face_count=1,
                        verification_status="approved",
                        image_width=width,
                        image_height=height,
                        capture_number=sequence,
                        device_info=device_info,
                    )
                    db.add(capture)
                    db.flush()
                    db.add(
                        AttendanceCaptureImage(
                            capture_id=capture.id,
                            session_id=session_id,
                            cycle_id=student_id,
                            capture_number=sequence,
                            file_name=filename,
                            content_type="image/jpeg",
                            image_bytes=image_bytes,
                            byte_size=len(image_bytes),
                        )
                    )
                    captures.append(capture)

                session.total_cycles_completed += 1
                session.total_images_collected += len(captures)
                db.commit()
                for capture in captures:
                    db.refresh(capture)
                logger.info("Dataset Approved: %s", student_id)
                logger.info("Dataset Saved: %s (%d images)", student_id, len(captures))
                return student_id, captures
        except Exception:
            logger.exception("Database failure while saving %s", student_id)
            raise

    def approve_cycle(
        self,
        session_id: str,
        cycle_number: int,
        frames: Sequence[np.ndarray],
        capture_times: Sequence[datetime],
        device_info: str = "Browser webcam",
    ) -> List[AttendanceCapture]:
        student_id, captures = self.save_student_dataset(
            session_id, frames, capture_times, device_info
        )
        return captures

    def reject_cycle(self, session_id: str, cycle_number: int) -> None:
        logger.info("Cycle Rejected: %s/cycle_%03d", session_id, cycle_number)

    def get_session_captures(self, session_id: str) -> List[AttendanceCapture]:
        with SessionLocal() as db:
            return (
                db.query(AttendanceCapture)
                .filter_by(session_id=session_id)
                .order_by(AttendanceCapture.cycle_id, AttendanceCapture.capture_number)
                .all()
            )

    def add_capture(
        self,
        session_id: str,
        image_path: str,
        face_count: int,
        image_width: int,
        image_height: int,
        capture_number: int,
        device_info: Optional[str] = None,
    ) -> AttendanceCapture:
        """Compatibility method for existing single-image collection pages."""
        with SessionLocal() as db:
            capture = AttendanceCapture(
                session_id=session_id,
                cycle_id="dataset",
                image_path=image_path,
                capture_time=datetime.now(timezone.utc),
                face_count=face_count,
                verification_status="accepted" if face_count == 1 else "rejected",
                image_width=image_width,
                image_height=image_height,
                capture_number=capture_number,
                device_info=device_info,
            )
            db.add(capture)
            db.commit()
            db.refresh(capture)
            return capture

    def update_session_image_count(self, session_id: str) -> Optional[AttendanceSession]:
        with SessionLocal() as db:
            session = db.query(AttendanceSession).filter_by(session_id=session_id).first()
            if session is None:
                return None
            session.total_images_collected = (
                db.query(func.count(AttendanceCapture.id))
                .filter_by(session_id=session_id, verification_status="approved")
                .scalar()
                or 0
            )
            db.commit()
            db.refresh(session)
            return session

    def get_session_statistics(self, session_id: str) -> Dict:
        with SessionLocal() as db:
            session = db.query(AttendanceSession).filter_by(session_id=session_id).first()
            if session is None:
                return {}
            total = db.query(func.count(AttendanceCapture.id)).filter_by(
                session_id=session_id
            ).scalar() or 0
            return {
                "session_id": session_id,
                "status": session.status,
                "total_captures": total,
                "accepted": total,
                "rejected": 0,
                "acceptance_rate": 100.0 if total else 0.0,
                "total_cycles": session.total_cycles_completed,
                "total_students_collected": session.total_cycles_completed,
                "session_start": session.session_start,
                "session_end": session.session_end,
                "duration_minutes": session.duration_minutes,
            }

    def create_or_get_student(
        self,
        name: str,
        roll_no: Optional[str] = None,
        department: Optional[str] = None,
        semester: Optional[str] = None,
    ) -> Optional[Student]:
        with SessionLocal() as db:
            if roll_no:
                student = db.query(Student).filter_by(roll_no=roll_no).first()
                if student:
                    return student
            student = Student(
                name=name,
                roll_no=roll_no or f"GEN-{uuid.uuid4().hex[:8].upper()}",
                department=department or "Unknown",
                semester=semester or "Unknown",
            )
            db.add(student)
            db.commit()
            db.refresh(student)
            return student

    def create_collection_session(self, student_name: str, **kwargs) -> Optional[Dict]:
        target_images = int(kwargs.pop("target_images", TARGET_IMAGES))
        student = self.create_or_get_student(name=student_name, **kwargs)
        if student is None:
            return None
        session = self.create_session(
            user_name=student_name,
            duration_minutes=max(1, target_images * 2),
            student_id=student.id,
            collection_type="dataset",
        )
        return {
            "session_id": session.session_id,
            "student_id": student.id,
            "student_name": student.name,
            "target_images": target_images,
        }
