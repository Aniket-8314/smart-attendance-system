"""WebRTC video processor — facecam capture pattern with thread-safe queue."""

import logging
import queue
import threading
import time
from datetime import datetime, timezone
from typing import List, Optional

import av
import cv2
import numpy as np
from streamlit_webrtc import VideoProcessorBase

from backend.face_detection_service import FaceDetectionService

logger = logging.getLogger(__name__)


class AttendanceVideoProcessor(VideoProcessorBase):
    """Detect faces in worker thread; push captures via queue for main thread."""

    capture_interval_seconds = 0.75
    face_log_interval_seconds = 3.0

    def __init__(self):
        started = time.perf_counter()
        self._created_at = started
        self._lock = threading.RLock()
        self.detector = FaceDetectionService()
        self._detector_thread: Optional[threading.Thread] = None
        self._first_frame_received = False
        self.capture_queue: queue.Queue = queue.Queue()
        self.last_capture_time = 0.0
        self.last_face_count = 0
        self.face_status = "Waiting for camera"
        self.quality_message = ""
        self.deadline_epoch = float("inf")
        self.camera_error = None
        self.capture_paused = False
        self.latest_frame: Optional[np.ndarray] = None
        self._last_face_log = 0.0
        self._capture_count = 0
        logger.info(
            "WebRTC video processor created in %.3fs (detector not loaded)",
            time.perf_counter() - started,
        )

    def _start_detector_initialization(self) -> None:
        with self._lock:
            if self._detector_thread is not None:
                return
            self.face_status = "Initializing Face Detector"
            self._detector_thread = threading.Thread(
                target=self.detector.initialize,
                name="attendance-face-detector-init",
                daemon=True,
            )
            self._detector_thread.start()

    def set_deadline(self, deadline_epoch: float) -> None:
        with self._lock:
            self.deadline_epoch = deadline_epoch

    def pause_capture(self) -> None:
        with self._lock:
            self.capture_paused = True

    def resume_capture(self) -> None:
        with self._lock:
            self.capture_paused = False
            self.last_capture_time = 0.0

    def clear_buffer(self) -> None:
        with self._lock:
            while not self.capture_queue.empty():
                try:
                    self.capture_queue.get_nowait()
                except queue.Empty:
                    break

    def _log_face_count(self, face_count: int) -> None:
        now = time.time()
        if now - self._last_face_log >= self.face_log_interval_seconds:
            self._last_face_log = now
            logger.info("Face Count = %s", face_count)

    def _enqueue_capture(self, image: np.ndarray, face_count: int) -> None:
        payload = {
            "image": image.copy(),
            "capture_time": datetime.now(timezone.utc),
            "face_count": face_count,
        }
        self.capture_queue.put(payload)
        self._capture_count += 1
        logger.info("Capture Triggered")
        logger.info("Image Added to queue (queue size = %s)", self.capture_queue.qsize())
        logger.info("Captured Image Count = %s", self._capture_count)

    def _process_frame(self, frame: av.VideoFrame) -> av.VideoFrame:
        image = frame.to_ndarray(format="bgr24")
        now = time.time()

        with self._lock:
            self.latest_frame = image.copy()

        if not self._first_frame_received:
            with self._lock:
                if not self._first_frame_received:
                    self._first_frame_received = True
                    logger.info(
                        "First Frame Received after %.3fs",
                        time.perf_counter() - self._created_at,
                    )
            self._start_detector_initialization()

        detector_info = self.detector.get_detector_info()
        if not detector_info["initialized"]:
            with self._lock:
                if detector_info["initialization_error"]:
                    self.face_status = "Face Detector Unavailable"
                    self.camera_error = detector_info["initialization_error"]
                else:
                    self.face_status = "Initializing Face Detector"
            cv2.putText(
                image,
                self.face_status,
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                (0, 180, 255),
                2,
            )
            return av.VideoFrame.from_ndarray(image, format="bgr24")

        try:
            face_count, face_data = self.detector.detect_faces(image)
            with self._lock:
                self.last_face_count = face_count
            self._log_face_count(face_count)

            if face_count == 0:
                status = "No Face Detected"
            elif face_count > 1:
                status = "Multiple Faces Detected"
            else:
                status = "Single Face Detected"

            with self._lock:
                self.face_status = status
                can_capture = (
                    not self.capture_paused
                    and now < self.deadline_epoch
                    and face_count == 1
                    and now - self.last_capture_time >= self.capture_interval_seconds
                )

            if can_capture:
                logger.info("Capture condition met (face_count=1, interval elapsed)")
                valid, message, blur_score = self.detector.validate_capture(image, face_data)
                with self._lock:
                    self.quality_message = message
                if not valid:
                    logger.info(
                        "Validation advisory (capture still allowed): %s (blur=%.1f)",
                        message,
                        blur_score,
                    )
                with self._lock:
                    if not self.capture_paused:
                        self._enqueue_capture(image, face_count)
                        self.last_capture_time = now

            annotated = self.detector.draw_faces_on_frame(image, face_data)
            color = (40, 220, 80) if face_count == 1 else (40, 80, 240)
            cv2.putText(
                annotated,
                status,
                (20, 35),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.8,
                color,
                2,
            )
            cv2.putText(
                annotated,
                f"Faces Detected: {face_count}",
                (20, 70),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 255, 0),
                2,
            )
            return av.VideoFrame.from_ndarray(annotated, format="bgr24")
        except Exception as exc:
            logger.exception("Camera frame processing error")
            with self._lock:
                self.camera_error = str(exc)
            return frame

    def recv(self, frame: av.VideoFrame) -> av.VideoFrame:
        return self._process_frame(frame)

    async def recv_queued(self, frames: List[av.VideoFrame]) -> List[av.VideoFrame]:
        if not frames:
            return []
        output = None
        for frame in frames:
            output = self._process_frame(frame)
        return [output]

    def snapshot(self) -> dict:
        with self._lock:
            return {
                "face_status": self.face_status,
                "face_count": self.last_face_count,
                "quality_message": self.quality_message,
                "camera_error": self.camera_error,
                "first_frame_received": self._first_frame_received,
                "queue_size": self.capture_queue.qsize(),
                "capture_count": self._capture_count,
                "detector": self.detector.get_detector_info(),
            }

    def pop_capture(self):
        try:
            return self.capture_queue.get_nowait()
        except queue.Empty:
            return None

    def capture_test_frame(self) -> Optional[dict]:
        """Manual test capture bypassing face detection."""
        with self._lock:
            if self.latest_frame is None:
                return None
            payload = {
                "image": self.latest_frame.copy(),
                "capture_time": datetime.now(timezone.utc),
                "face_count": 0,
            }
        logger.info("Capture Test Image triggered from main thread")
        return payload
