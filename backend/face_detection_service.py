"""Lazy face detection with MediaPipe, Haar, and Dlib fallbacks."""

import importlib.util
import logging
import os
import threading
import time
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

logger = logging.getLogger(__name__)


class FaceDetectionService:
    """Initialize a detector once, on demand, outside WebRTC signalling."""

    def __init__(self, blur_threshold: float = 80.0):
        self.blur_threshold = blur_threshold
        self.detector_type: Optional[str] = None
        self.face_detector = None
        self.initialized = False
        self.initializing = False
        self.initialization_error: Optional[str] = None
        self.initialization_seconds: Optional[float] = None
        self._lock = threading.RLock()

    def initialize(self) -> bool:
        with self._lock:
            if self.initialized:
                return True
            if self.initializing:
                return False
            self.initializing = True

        started = time.perf_counter()
        logger.info("FaceDetectionService Init Started")
        try:
            if self._initialize_mediapipe():
                return True
            if self._initialize_haar():
                return True
            if self._initialize_dlib():
                return True
            raise RuntimeError("No supported face detector could be initialized")
        except Exception as exc:
            with self._lock:
                self.initialization_error = str(exc)
            logger.exception("FaceDetectionService initialization failed")
            return False
        finally:
            elapsed = time.perf_counter() - started
            with self._lock:
                self.initializing = False
                self.initialization_seconds = elapsed
            logger.info(
                "FaceDetectionService Init Finished in %.3fs (detector=%s)",
                elapsed,
                self.detector_type,
            )

    def _initialize_mediapipe(self) -> bool:
        started = time.perf_counter()
        logger.info("MediaPipe Init Started")
        try:
            spec = importlib.util.find_spec("mediapipe")
            if spec is None or not spec.submodule_search_locations:
                logger.warning("MediaPipe is not installed")
                return False

            package_dir = next(iter(spec.submodule_search_locations))
            legacy_solutions = os.path.join(package_dir, "python", "solutions")
            if not os.path.isdir(legacy_solutions):
                logger.warning(
                    "MediaPipe installation has no solutions API at %s; skipping it",
                    legacy_solutions,
                )
                return False

            import mediapipe as mp

            solutions = getattr(mp, "solutions", None)
            if solutions is None:
                logger.warning("MediaPipe imported without mp.solutions")
                return False
            detector = solutions.face_detection.FaceDetection(
                model_selection=0,
                min_detection_confidence=0.6,
            )
            with self._lock:
                self.face_detector = detector
                self.detector_type = "mediapipe"
                self.initialized = True
            return True
        except Exception:
            logger.exception("MediaPipe initialization failed; using fallback")
            return False
        finally:
            logger.info("MediaPipe Init Finished in %.3fs", time.perf_counter() - started)

    def _initialize_haar(self) -> bool:
        started = time.perf_counter()
        try:
            cascade_path = (
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
            )
            detector = cv2.CascadeClassifier(cascade_path)
            if detector.empty():
                return False
            with self._lock:
                self.face_detector = detector
                self.detector_type = "haar_cascade"
                self.initialized = True
            logger.info("OpenCV Haar Cascade initialized in %.3fs", time.perf_counter() - started)
            return True
        except Exception:
            logger.exception("OpenCV Haar Cascade initialization failed")
            return False

    def _initialize_dlib(self) -> bool:
        started = time.perf_counter()
        try:
            import dlib

            detector = dlib.get_frontal_face_detector()
            with self._lock:
                self.face_detector = detector
                self.detector_type = "dlib"
                self.initialized = True
            logger.info("Dlib initialized in %.3fs", time.perf_counter() - started)
            return True
        except Exception:
            logger.exception("Dlib initialization failed")
            return False

    def detect_faces(self, frame: np.ndarray) -> Tuple[int, List[Dict]]:
        if not self.initialized:
            return 0, []
        try:
            if self.detector_type == "mediapipe":
                return self._detect_mediapipe(frame)
            if self.detector_type == "haar_cascade":
                return self._detect_haar(frame)
            if self.detector_type == "dlib":
                return self._detect_dlib(frame)
            return 0, []
        except Exception:
            logger.exception("Face Detection Error (%s)", self.detector_type)
            return 0, []

    def _detect_mediapipe(self, frame: np.ndarray) -> Tuple[int, List[Dict]]:
        height, width = frame.shape[:2]
        result = self.face_detector.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        faces = []
        for detection in result.detections or []:
            box = detection.location_data.relative_bounding_box
            x1 = max(0, int(box.xmin * width))
            y1 = max(0, int(box.ymin * height))
            x2 = min(width, int((box.xmin + box.width) * width))
            y2 = min(height, int((box.ymin + box.height) * height))
            faces.append({
                "bbox": (x1, y1, x2, y2),
                "confidence": float(detection.score[0]),
            })
        return len(faces), faces

    def _detect_haar(self, frame: np.ndarray) -> Tuple[int, List[Dict]]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        boxes = self.face_detector.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        faces = [
            {"bbox": (x, y, x + width, y + height), "confidence": 0.7}
            for x, y, width, height in boxes
        ]
        return len(faces), faces

    def _detect_dlib(self, frame: np.ndarray) -> Tuple[int, List[Dict]]:
        height, width = frame.shape[:2]
        detections = self.face_detector(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB), 0)
        faces = [
            {
                "bbox": (
                    max(0, face.left()), max(0, face.top()),
                    min(width, face.right()), min(height, face.bottom()),
                ),
                "confidence": 0.7,
            }
            for face in detections
        ]
        return len(faces), faces

    def validate_capture(
        self,
        frame: np.ndarray,
        face_data: List[Dict],
        previous_frame: np.ndarray = None,
    ) -> Tuple[bool, str, float]:
        if len(face_data) != 1:
            return False, "Exactly one face is required", 0.0
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = face_data[0]["bbox"]
        margin_x, margin_y = int(width * 0.02), int(height * 0.02)
        if x1 <= margin_x or y1 <= margin_y or x2 >= width - margin_x or y2 >= height - margin_y:
            return False, "Face is partially outside the frame", 0.0
        if (x2 - x1) < width * 0.12 or (y2 - y1) < height * 0.12:
            return False, "Move closer to the camera", 0.0
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blur_score = float(cv2.Laplacian(gray, cv2.CV_64F).var())
        if blur_score < self.blur_threshold:
            return False, "Image is blurred", blur_score
        if previous_frame is not None:
            current = cv2.resize(gray, (64, 64))
            previous = cv2.resize(
                cv2.cvtColor(previous_frame, cv2.COLOR_BGR2GRAY), (64, 64)
            )
            if float(cv2.absdiff(current, previous).mean()) < 1.5:
                return False, "Waiting for a distinct frame", blur_score
        return True, "Valid image", blur_score

    def draw_faces_on_frame(self, frame: np.ndarray, face_data: List[Dict]) -> np.ndarray:
        output = frame.copy()
        for face in face_data:
            x1, y1, x2, y2 = face["bbox"]
            cv2.rectangle(output, (x1, y1), (x2, y2), (40, 220, 80), 2)
        return output

    def get_detector_info(self) -> Dict:
        with self._lock:
            return {
                "detector_type": self.detector_type,
                "initialized": self.initialized,
                "initializing": self.initializing,
                "initialization_error": self.initialization_error,
                "initialization_seconds": self.initialization_seconds,
            }

    def close(self) -> None:
        if self.detector_type == "mediapipe" and self.face_detector is not None:
            self.face_detector.close()
