import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

import cv2
import numpy as np
import av
from sqlalchemy import MetaData, create_engine, inspect, text
from sqlalchemy.orm import sessionmaker


class AttendanceWorkflowTest(unittest.TestCase):
    def test_legacy_schema_adds_cycle_columns(self):
        from database.schema import initialize_database

        engine = create_engine("sqlite:///:memory:")
        with engine.begin() as connection:
            connection.execute(text("""
                CREATE TABLE attendance_sessions (
                    id INTEGER PRIMARY KEY,
                    session_id VARCHAR NOT NULL,
                    user_name VARCHAR NOT NULL,
                    duration_minutes INTEGER NOT NULL
                )
            """))
            connection.execute(text("""
                CREATE TABLE attendance_captures (
                    id INTEGER PRIMARY KEY,
                    session_id VARCHAR NOT NULL,
                    image_path VARCHAR NOT NULL,
                    capture_number INTEGER NOT NULL
                )
            """))

        class EmptyBase:
            metadata = MetaData()

        initialize_database(engine, EmptyBase)
        session_columns = {
            column["name"]
            for column in inspect(engine).get_columns("attendance_sessions")
        }
        capture_columns = {
            column["name"]
            for column in inspect(engine).get_columns("attendance_captures")
        }
        self.assertIn("collection_type", session_columns)
        self.assertIn("total_cycles_completed", session_columns)
        self.assertIn("cycle_id", capture_columns)

    def test_new_attendance_schema_allows_session_without_student(self):
        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
        from database.models import AttendanceCaptureImage, AttendanceSession, Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        columns = {
            column["name"]: column
            for column in inspect(engine).get_columns(AttendanceSession.__tablename__)
        }
        self.assertTrue(columns["student_id"]["nullable"])
        image_columns = {
            column["name"]
            for column in inspect(engine).get_columns(AttendanceCaptureImage.__tablename__)
        }
        self.assertIn("image_bytes", image_columns)
        self.assertIn("content_type", image_columns)

    def test_save_student_dataset_stores_images_in_database(self):
        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
        from backend import attendance_service as attendance_module
        from backend.attendance_service import AttendanceService, TARGET_IMAGES
        from database.models import AttendanceCaptureImage, Base

        engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(bind=engine)
        Base.metadata.create_all(engine)

        original_engine = attendance_module.engine
        original_session_local = attendance_module.SessionLocal
        attendance_module.engine = engine
        attendance_module.SessionLocal = TestingSessionLocal
        try:
            service = AttendanceService()
            session = service.create_session("Instructor", 5)
            frames = [
                np.full((24, 32, 3), value, dtype=np.uint8)
                for value in range(TARGET_IMAGES)
            ]
            times = [datetime.now(timezone.utc) for _ in range(TARGET_IMAGES)]

            student_id, captures = service.save_student_dataset(
                session.session_id,
                frames,
                times,
            )

            self.assertEqual("STD_000001", student_id)
            self.assertEqual(TARGET_IMAGES, len(captures))
            with TestingSessionLocal() as db:
                rows = db.query(AttendanceCaptureImage).all()
                self.assertEqual(TARGET_IMAGES, len(rows))
                self.assertEqual("image/jpeg", rows[0].content_type)
                self.assertGreater(rows[0].byte_size, 0)
                self.assertTrue(rows[0].image_bytes.startswith(b"\xff\xd8"))
        finally:
            attendance_module.engine = original_engine
            attendance_module.SessionLocal = original_session_local

    def test_quality_validation_rejects_blur_boundary_and_duplicates(self):
        from backend.face_detection_service import FaceDetectionService

        service = FaceDetectionService.__new__(FaceDetectionService)
        service.blur_threshold = 80.0
        sharp = np.zeros((480, 640, 3), dtype=np.uint8)
        for y in range(0, 480, 20):
            for x in range(0, 640, 20):
                if (x // 20 + y // 20) % 2:
                    sharp[y:y + 20, x:x + 20] = 255

        valid_face = [{"bbox": (180, 100, 460, 400), "confidence": 0.9}]
        valid, _, _ = service.validate_capture(sharp, valid_face)
        self.assertTrue(valid)

        blurred = cv2.GaussianBlur(sharp, (51, 51), 0)
        valid, message, _ = service.validate_capture(blurred, valid_face)
        self.assertFalse(valid)
        self.assertIn("blurred", message)

        boundary_face = [{"bbox": (0, 100, 300, 400), "confidence": 0.9}]
        valid, message, _ = service.validate_capture(sharp, boundary_face)
        self.assertFalse(valid)
        self.assertIn("outside", message)

        valid, message, _ = service.validate_capture(sharp, valid_face, sharp.copy())
        self.assertFalse(valid)
        self.assertIn("distinct", message)

    def test_video_processor_factory_is_lightweight_and_detector_is_lazy(self):
        import time

        from backend.capture_processor import AttendanceVideoProcessor

        started = time.perf_counter()
        processor = AttendanceVideoProcessor()
        self.assertLess(time.perf_counter() - started, 0.5)
        self.assertFalse(processor.detector.get_detector_info()["initialized"])

        frame = av.VideoFrame.from_ndarray(
            np.zeros((240, 320, 3), dtype=np.uint8),
            format="bgr24",
        )
        started = time.perf_counter()
        processor.recv(frame)
        self.assertLess(time.perf_counter() - started, 0.5)
        snapshot = processor.snapshot()
        self.assertTrue(snapshot["first_frame_received"])
        self.assertEqual(snapshot["queue_size"], 0)

        deadline = time.perf_counter() + 2
        while time.perf_counter() < deadline:
            info = processor.detector.get_detector_info()
            if info["initialized"] or info["initialization_error"]:
                break
            time.sleep(0.01)

        info = processor.detector.get_detector_info()
        self.assertTrue(info["initialized"], info["initialization_error"])
        self.assertLess(info["initialization_seconds"], 2)


if __name__ == "__main__":
    unittest.main()
