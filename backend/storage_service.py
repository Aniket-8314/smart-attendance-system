"""Supabase Storage helpers for attendance and student reference images."""

from __future__ import annotations

import logging
import uuid
from pathlib import PurePosixPath
from typing import Optional, Sequence

from database.db import ATTENDANCE_SESSIONS_BUCKET, STUDENT_IMAGES_BUCKET, supabase

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, client=None):
        self.client = client or supabase
        if self.client is None:
            raise RuntimeError("SUPABASE_URL and SUPABASE_KEY are required for storage operations")

    @staticmethod
    def _normalize_segment(value: str) -> str:
        return "".join(character if character.isalnum() or character in {"-", "_"} else "_" for character in value.strip())

    @staticmethod
    def _filename(extension: str = "jpg", prefix: str = "image") -> str:
        return f"{prefix}_{uuid.uuid4().hex}.{extension.lstrip('.')}"

    def student_image_path(self, roll_no: str, filename: Optional[str] = None) -> str:
        safe_roll = self._normalize_segment(roll_no)
        safe_filename = PurePosixPath(filename).name if filename else self._filename()
        return str(PurePosixPath(safe_roll) / safe_filename)

    def attendance_capture_path(self, session_id: str, filename: Optional[str] = None) -> str:
        safe_session = self._normalize_segment(session_id)
        safe_filename = PurePosixPath(filename).name if filename else self._filename(prefix="capture")
        return str(PurePosixPath(safe_session) / safe_filename)

    def upload_student_image(self, roll_no: str, image_bytes: bytes, content_type: str = "image/jpeg", filename: Optional[str] = None) -> str:
        path = self.student_image_path(roll_no, filename)
        self.client.storage.from_(STUDENT_IMAGES_BUCKET).upload(
            path,
            image_bytes,
            file_options={"content-type": content_type},
        )
        logger.info("Uploaded student image: %s/%s", STUDENT_IMAGES_BUCKET, path)
        return path

    def upload_attendance_capture(self, session_id: str, image_bytes: bytes, content_type: str = "image/jpeg", filename: Optional[str] = None) -> str:
        path = self.attendance_capture_path(session_id, filename)
        self.client.storage.from_(ATTENDANCE_SESSIONS_BUCKET).upload(
            path,
            image_bytes,
            file_options={"content-type": content_type},
        )
        logger.info("Uploaded attendance capture: %s/%s", ATTENDANCE_SESSIONS_BUCKET, path)
        return path

    def delete_student_images(self, roll_no: str, image_paths: Optional[Sequence[str]] = None) -> int:
        """
        Delete every stored reference image for a student.

        The database is the source of truth for known files, but we also sweep the
        student's storage folder so orphaned objects from earlier failed updates are
        removed too.
        """
        bucket = self.client.storage.from_(STUDENT_IMAGES_BUCKET)
        safe_roll = self._normalize_segment(roll_no)

        paths_to_delete = {str(PurePosixPath(path)) for path in (image_paths or []) if path}

        try:
            folder_entries = bucket.list(safe_roll)
            for entry in folder_entries or []:
                filename = entry.get("name") if isinstance(entry, dict) else None
                if filename:
                    paths_to_delete.add(str(PurePosixPath(safe_roll) / filename))
        except Exception as exc:
            logger.warning("Could not list student image folder %s: %s", safe_roll, exc)

        if not paths_to_delete:
            logger.info("No student images found for %s", roll_no)
            return 0

        bucket.remove(sorted(paths_to_delete))
        logger.info("Deleted %d student images from %s/%s", len(paths_to_delete), STUDENT_IMAGES_BUCKET, safe_roll)
        return len(paths_to_delete)

    def get_public_url(self, bucket: str, path: str) -> str:
        return self.client.storage.from_(bucket).get_public_url(path)
