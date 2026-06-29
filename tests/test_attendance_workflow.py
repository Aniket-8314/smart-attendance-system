import os
import time
import unittest
from datetime import datetime, timezone

import av
import numpy as np
from sqlalchemy import create_engine, inspect
from sqlalchemy.orm import sessionmaker


class FakeStorageService:
    def __init__(self):
        self.student_uploads = []
        self.capture_uploads = []
        self.deleted_student_paths = []
        self.folder_listings = {}

    def upload_student_image(self, roll_no, image_bytes, content_type="image/jpeg", filename=None):
        path = f"{roll_no}/{filename or 'student.jpg'}"
        self.student_uploads.append((path, image_bytes, content_type))
        return path

    def upload_attendance_capture(self, session_id, image_bytes, content_type="image/jpeg", filename=None):
        path = f"{session_id}/{filename or 'capture.jpg'}"
        self.capture_uploads.append((path, image_bytes, content_type))
        return path

    def get_public_url(self, bucket, path):
        return f"https://example.test/{bucket}/{path}"

    def delete_student_images(self, roll_no, image_paths=None):
        paths = set(image_paths or [])
        for entry in self.folder_listings.get(roll_no, []):
            paths.add(f"{roll_no}/{entry}")
        self.deleted_student_paths.append((roll_no, sorted(paths)))
        return len(paths)


class AttendanceWorkflowTest(unittest.TestCase):
    def setUp(self):
        os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")

    def _prepare_service(self):
        from database.models import Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)
        TestingSessionLocal = sessionmaker(bind=engine)

        import backend.attendance_service as attendance_module

        original_engine = attendance_module.engine
        original_session_local = attendance_module.SessionLocal
        attendance_module.engine = engine
        attendance_module.SessionLocal = TestingSessionLocal

        service = attendance_module.AttendanceService(storage=FakeStorageService())
        return service, engine, TestingSessionLocal, attendance_module, original_engine, original_session_local

    def test_normalized_schema_is_defined(self):
        from database.models import AttendanceCapture, AttendanceRecord, AttendanceSession, Student, StudentImage, Base

        engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(engine)

        table_names = inspect(engine).get_table_names()
        self.assertEqual(
            {"students", "student_images", "attendance_sessions", "attendance_captures", "attendance_records"},
            set(table_names),
        )

        student_columns = {column["name"] for column in inspect(engine).get_columns(Student.__tablename__)}
        self.assertTrue({"roll_no", "name", "dept", "sem"}.issubset(student_columns))

        session_columns = {column["name"] for column in inspect(engine).get_columns(AttendanceSession.__tablename__)}
        self.assertTrue({"session_id", "prof_name", "course_name", "start_time", "end_time", "expected_students", "captured_students", "status"}.issubset(session_columns))

        capture_columns = {column["name"] for column in inspect(engine).get_columns(AttendanceCapture.__tablename__)}
        self.assertTrue({"capture_id", "session_id", "image_path", "capture_time"}.issubset(capture_columns))

        record_columns = {column["name"] for column in inspect(engine).get_columns(AttendanceRecord.__tablename__)}
        self.assertTrue({"record_id", "session_id", "roll_no", "confidence_score", "marked_at", "status"}.issubset(record_columns))

        image_columns = {column["name"] for column in inspect(engine).get_columns(StudentImage.__tablename__)}
        self.assertTrue({"image_id", "roll_no", "image_path", "uploaded_at"}.issubset(image_columns))

    def test_student_image_and_attendance_workflow(self):
        service, engine, session_local, module, original_engine, original_session_local = self._prepare_service()
        try:
            student = service.create_or_update_student("2401ME01", "Asha", "Mechanical", "6")
            self.assertEqual("2401ME01", student.roll_no)

            student_image = service.add_student_image(
                "2401ME01",
                b"\xff\xd8\xff\xdbtest-image",
                filename="img1.jpg",
            )
            self.assertEqual("2401ME01/img1.jpg", student_image.image_path)
            self.assertEqual(1, len(service.list_student_images("2401ME01")))

            session = service.create_session("Professor Sharma", "Computer Networks", expected_students=25)
            capture = service.add_capture(session.session_id, b"\xff\xd8\xff\xdbcapture", filename="capture_1.jpg")
            self.assertEqual(f"{session.session_id}/capture_1.jpg", capture.image_path)

            record = service.add_attendance_record(
                session.session_id,
                "2401ME01",
                0.93,
                status="PRESENT",
                marked_at=datetime.now(timezone.utc),
            )
            duplicate = service.add_attendance_record(
                session.session_id,
                "2401ME01",
                0.75,
                status="MANUALLY_VERIFIED",
            )
            self.assertEqual(record.record_id, duplicate.record_id)

            closed = service.close_session(session.session_id)
            self.assertEqual("CLOSED", closed.status)
            self.assertEqual(1, closed.captured_students)

            stats = service.get_session_statistics(session.session_id)
            self.assertEqual(1, stats["capture_count"])
            self.assertEqual(1, stats["record_count"])
            self.assertEqual(1, stats["present_count"])
        finally:
            module.engine = original_engine
            module.SessionLocal = original_session_local

    def test_delete_student_images_removes_storage_and_database_rows(self):
        service, engine, session_local, module, original_engine, original_session_local = self._prepare_service()
        try:
            service.create_or_update_student("2401ME03", "Nina", "IT", "4")
            first_image = service.add_student_image("2401ME03", b"img-one", filename="old_1.jpg")
            second_image = service.add_student_image("2401ME03", b"img-two", filename="old_2.jpg")

            service.storage.folder_listings["2401ME03"] = ["old_1.jpg", "old_2.jpg", "orphan.jpg"]

            deleted_count = service.delete_student_images("2401ME03")

            self.assertEqual(2, deleted_count)
            self.assertEqual(
                [
                    (
                        "2401ME03",
                        [
                            "2401ME03/old_1.jpg",
                            "2401ME03/old_2.jpg",
                            "2401ME03/orphan.jpg",
                        ],
                    )
                ],
                service.storage.deleted_student_paths,
            )
            self.assertEqual([], service.list_student_images("2401ME03"))
        finally:
            module.engine = original_engine
            module.SessionLocal = original_session_local

    def test_confidence_score_validation(self):
        service, engine, session_local, module, original_engine, original_session_local = self._prepare_service()
        try:
            service.create_or_update_student("2401ME02", "Ravi", "ECE", "5")
            session = service.create_session("Prof", "Signals")
            with self.assertRaises(ValueError):
                service.add_attendance_record(session.session_id, "2401ME02", 1.5)
        finally:
            module.engine = original_engine
            module.SessionLocal = original_session_local

    def test_video_processor_factory_is_lightweight_and_detector_is_lazy(self):
        from backend.capture_processor import AttendanceVideoProcessor

        started = time.perf_counter()
        processor = AttendanceVideoProcessor()
        self.assertLess(time.perf_counter() - started, 0.5)
        self.assertFalse(processor.detector.get_detector_info()["initialized"])

        frame = av.VideoFrame.from_ndarray(np.zeros((240, 320, 3), dtype=np.uint8), format="bgr24")
        started = time.perf_counter()
        processor.recv(frame)
        self.assertLess(time.perf_counter() - started, 0.5)
        snapshot = processor.snapshot()
        self.assertTrue(snapshot["first_frame_received"])


if __name__ == "__main__":
    unittest.main()
