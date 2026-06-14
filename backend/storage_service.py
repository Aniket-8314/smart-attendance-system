"""Filesystem storage for approved attendance student datasets."""

import logging
import os
import shutil
import uuid
from datetime import datetime
from pathlib import Path
from typing import List, Sequence, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class StorageService:
    def __init__(self, base_path: str = None):
        project_root = Path(__file__).resolve().parent.parent
        self.base_path = Path(base_path or project_root / "attendance_dataset")
        self.base_path.mkdir(parents=True, exist_ok=True)

    def get_session_directory(self, session_id: str) -> Path:
        path = self.base_path / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def get_student_directory(self, session_id: str, student_id: str) -> Path:
        return self.get_session_directory(session_id) / student_id

    def save_student_images(
        self,
        frames: Sequence[np.ndarray],
        session_id: str,
        student_id: str,
    ) -> List[Tuple[str, int, int]]:
        """Write attendance_dataset/session_id/student_id/image_NNN.jpg."""
        if not frames:
            raise ValueError("Cannot save an empty student dataset")

        final_dir = self.get_student_directory(session_id, student_id)
        if final_dir.exists():
            raise FileExistsError(f"Student dataset already exists: {final_dir}")

        temp_dir = final_dir.with_name(f".{student_id}-{uuid.uuid4().hex}.tmp")
        temp_dir.mkdir(parents=True, exist_ok=False)
        saved: List[Tuple[str, int, int]] = []

        try:
            for sequence, frame in enumerate(frames, start=1):
                filename = f"image_{sequence:03d}.jpg"
                path = temp_dir / filename
                if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92]):
                    raise OSError(f"Failed to write {path}")
                height, width = frame.shape[:2]
                relative = Path(session_id) / student_id / filename
                saved.append((str(relative), width, height))

            temp_dir.replace(final_dir)
            logger.info("Images Saved: %s/%s", session_id, student_id)
            return saved
        except Exception:
            shutil.rmtree(temp_dir, ignore_errors=True)
            logger.exception("Storage failure for %s/%s", session_id, student_id)
            raise

    def get_cycle_directory(self, session_id: str, cycle_id: str) -> Path:
        """Backward-compatible alias for student directory."""
        return self.get_student_directory(session_id, cycle_id)

    def save_cycle_images(
        self,
        frames: Sequence[np.ndarray],
        session_id: str,
        cycle_id: str,
    ) -> List[Tuple[str, int, int]]:
        return self.save_student_images(frames, session_id, cycle_id)

    def save_capture_image(
        self,
        frame: np.ndarray,
        session_id: str,
        capture_number: int,
    ) -> Tuple[str, int, int]:
        """Compatibility path for the existing single-image dataset page."""
        session_dir = self.get_session_directory(session_id)
        filename = (
            f"capture_{capture_number:03d}_"
            f"{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        )
        path = session_dir / filename
        if not cv2.imwrite(str(path), frame, [cv2.IMWRITE_JPEG_QUALITY, 92]):
            raise OSError(f"Failed to write {path}")
        height, width = frame.shape[:2]
        return str(Path(session_id) / filename), width, height

    def delete_student_dataset(self, session_id: str, student_id: str) -> None:
        shutil.rmtree(
            self.get_student_directory(session_id, student_id),
            ignore_errors=True,
        )

    def delete_cycle(self, session_id: str, cycle_id: str) -> None:
        self.delete_student_dataset(session_id, cycle_id)

    def get_session_images(self, session_id: str) -> List[str]:
        session_dir = self.get_session_directory(session_id)
        return sorted(
            str(path)
            for path in session_dir.rglob("*.jpg")
            if path.is_file()
        )

    def resolve_path(self, relative_path: str) -> str:
        return str(self.base_path / relative_path)

    def delete_session_directory(self, session_id: str) -> bool:
        session_dir = self.base_path / session_id
        if not session_dir.exists():
            return False
        shutil.rmtree(session_dir)
        return True
