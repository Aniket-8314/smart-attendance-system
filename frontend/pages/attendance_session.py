"""Live attendance dataset collection using a fixed 20-slot capture grid."""

import logging
import os
import sys
import time
from datetime import datetime

import cv2
import streamlit as st
from streamlit_webrtc import WebRtcMode, webrtc_streamer

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from backend.attendance_service import AttendanceService, TARGET_IMAGES
from backend.capture_processor import AttendanceVideoProcessor
from frontend.ui import apply_global_styles

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Attendance Collection", page_icon=":camera:", layout="wide")
apply_global_styles(max_width=1380)

st.markdown(
    """
    <style>
    .session-header {display:flex; justify-content:space-between; align-items:center;
      padding: 1rem 1.25rem; border-radius: 8px; color:#172033;
      background:#ffffff; border:1px solid #d9e2ec; margin-bottom:1rem;
      box-shadow:0 1px 2px rgba(16,24,40,.04);}
    .session-header h1 {font-size:1.7rem; margin:0;}
    .countdown {font: 700 1.6rem monospace; color:#ffffff; background:#b42318;
      padding:.35rem .75rem; border-radius:8px; position:sticky; top:.5rem; z-index:999;}
    .placeholder {border: 2px dashed #bcccdc; border-radius: 8px; height: 140px;
      display: flex; align-items: center; justify-content: center; color: #667085;
      background:#ffffff;
      font-size: 0.85rem; text-align: center;}
    .face-count-live {font-size: 1.1rem; font-weight: 600; padding: 0.5rem 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

required = (
    "current_session_id",
    "current_instructor_name",
    "session_duration_minutes",
    "session_start_epoch",
    "session_deadline_epoch",
)
if any(key not in st.session_state for key in required):
    st.error("No active attendance session was found.")
    if st.button("Start Attendance Session", type="primary"):
        st.switch_page("pages/start_attendance_session.py")
    st.stop()

session_id = st.session_state.current_session_id
deadline = st.session_state.session_deadline_epoch

for key, value in {
    "students_collected": 0,
    "captured_images": [None] * TARGET_IMAGES,
    "retake_slot": None,
    "cooldown_until": None,
    "save_success": None,
    "session_finalized": False,
    "pending_rerun": False,
}.items():
    st.session_state.setdefault(key, value)


@st.cache_resource
def get_attendance_service() -> AttendanceService:
    return AttendanceService()


def format_remaining(seconds: int) -> str:
    seconds = max(0, seconds)
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def filled_count() -> int:
    return sum(1 for item in st.session_state.captured_images if item is not None)


def next_student_label() -> str:
    return f"STD_{st.session_state.students_collected + 1:06d}"


def get_next_slot() -> int:
    if st.session_state.retake_slot is not None:
        slot = st.session_state.retake_slot
        st.session_state.retake_slot = None
        return slot
    return next(
        (index for index, value in enumerate(st.session_state.captured_images) if value is None),
        -1,
    )


def should_capture_images() -> bool:
    return (
        remaining > 0
        and st.session_state.cooldown_until is None
        and filled_count() < TARGET_IMAGES
    )


def drain_capture_queue(processor: AttendanceVideoProcessor) -> int:
    """Main Streamlit thread: move queued captures into fixed session_state slots."""
    if processor is None:
        return 0

    added = 0
    while True:
        payload = processor.pop_capture()
        if payload is None:
            break
        slot = get_next_slot()
        if slot == -1:
            logger.info("All fixed slots full; dropping queued frame")
            processor.clear_buffer()
            processor.pause_capture()
            break
        st.session_state.captured_images[slot] = payload
        added += 1
        logger.info("Slot Updated: slot %s", slot + 1)

    if filled_count() >= TARGET_IMAGES:
        processor.clear_buffer()
        processor.pause_capture()

    if added:
        logger.info(
            "Session State Updated: added=%s, slots_filled=%s, queue_remaining=%s",
            added,
            filled_count(),
            processor.snapshot()["queue_size"],
        )
        st.session_state.pending_rerun = True
    return added


def reset_capture_state(processor) -> None:
    st.session_state.captured_images = [None] * TARGET_IMAGES
    st.session_state.retake_slot = None
    st.session_state.save_success = None
    if processor:
        processor.clear_buffer()
        processor.resume_capture()


def finalize_session(status: str = "completed") -> None:
    if not st.session_state.session_finalized:
        get_attendance_service().end_session(session_id, status=status)
        st.session_state.session_finalized = True
    st.switch_page("pages/attendance_completion.py")


def default_snapshot() -> dict:
    return {
        "face_status": "Waiting for camera",
        "face_count": 0,
        "quality_message": "",
        "camera_error": None,
        "queue_size": 0,
        "capture_count": 0,
        "detector": {"initialized": False},
    }


def render_slot(index: int, processor) -> None:
    entry = st.session_state.captured_images[index]
    if entry is not None:
        image_rgb = cv2.cvtColor(entry["image"], cv2.COLOR_BGR2RGB)
        st.image(image_rgb, channels="RGB", caption="Captured Image", use_container_width=True)
        if st.button("Retake", key=f"retake_{index}", use_container_width=True):
            st.session_state.captured_images[index] = None
            st.session_state.retake_slot = index
            logger.info("Image Retaken: slot %s", index + 1)
            if processor:
                processor.clear_buffer()
                processor.resume_capture()
            st.rerun()
    else:
        st.markdown(
            f"<div class='placeholder'>Slot {index + 1}<br>Waiting For Capture</div>",
            unsafe_allow_html=True,
        )


remaining = max(0, int(deadline - time.time()))
if remaining <= 0:
    finalize_session()

camera_should_run = should_capture_images()

st.markdown(
    f"""
    <div class="session-header">
      <h1>Attendance Collection</h1>
      <div class="countdown">{format_remaining(remaining)}</div>
    </div>
    """,
    unsafe_allow_html=True,
)

camera_col, panel_col = st.columns([1.55, 1], gap="large")

with camera_col:
    st.subheader("Live Camera")
    context = webrtc_streamer(
        key=f"attendance-camera-{session_id}",
        mode=WebRtcMode.SENDRECV,
        desired_playing_state=camera_should_run,
        media_stream_constraints={"video": True, "audio": False},
        video_processor_factory=AttendanceVideoProcessor,
        async_processing=True,
        video_html_attrs={"autoPlay": True, "controls": False, "muted": True},
    )
    processor = context.video_processor
    if processor:
        processor.set_deadline(deadline)
        if camera_should_run:
            processor.resume_capture()
        else:
            processor.clear_buffer()
            processor.pause_capture()

    if camera_should_run and not context.state.playing:
        st.info("Allow browser camera permission. The camera starts automatically.")

    if context.state.playing and processor:
        drain_capture_queue(processor)

active_processor = context.video_processor
snapshot = active_processor.snapshot() if active_processor else default_snapshot()

with panel_col:
    st.subheader("Status Information")
    st.markdown(
        f"<p class='face-count-live'>Faces Detected: <strong>{snapshot.get('face_count', 0)}</strong></p>",
        unsafe_allow_html=True,
    )

    if snapshot["camera_error"]:
        st.error(f"Camera error: {snapshot['camera_error']}")
    elif filled_count() >= TARGET_IMAGES:
        st.success("20 images captured. Face detection is stopped until a retake is requested.")
    elif snapshot["face_status"] == "Single Face Detected":
        st.success(f"Single Face Detected - {snapshot['quality_message'] or 'Ready to capture'}")
    elif snapshot["face_status"] == "Multiple Faces Detected":
        st.error("Multiple Faces Detected")
    elif snapshot["face_status"] == "Initializing Face Detector":
        st.info("Camera connected. Initializing face detector...")
    elif snapshot["face_status"] == "No Face Detected":
        st.warning("No Face Detected")
    else:
        st.info(snapshot["face_status"])

    row1 = st.columns(2)
    row1[0].metric("Session ID", session_id[:12] + "...")
    row1[1].metric("Instructor", st.session_state.current_instructor_name)
    row2 = st.columns(2)
    row2[0].metric("Students Collected", st.session_state.students_collected)
    row2[1].metric("Remaining Time", format_remaining(remaining))
    st.metric("Current Student ID", next_student_label())
    st.metric("Captured Images", f"{filled_count()} / {TARGET_IMAGES}")
    st.progress(filled_count() / TARGET_IMAGES)
    st.caption(
        f"Processor queue: {snapshot['queue_size']} - "
        f"Total captures: {snapshot['capture_count']} - "
        f"Quality: {snapshot['quality_message'] or 'n/a'}"
    )

logger.info("Rendering fixed grid with %s filled slots", filled_count())

st.divider()
st.subheader("Captured Images")

for row_start in range(0, TARGET_IMAGES, 5):
    columns = st.columns(5)
    for column, index in zip(columns, range(row_start, row_start + 5)):
        with column:
            render_slot(index, context.video_processor)

st.divider()

with st.expander("Debug Tools", expanded=False):
    if st.button("Capture Test Image", help="Bypass face detection to test fixed slot updates"):
        test_processor = context.video_processor
        if test_processor is None:
            st.warning("Camera processor not ready.")
        else:
            payload = test_processor.capture_test_frame()
            if payload is None:
                st.warning("No camera frame available yet.")
            else:
                slot = get_next_slot()
                if slot == -1:
                    st.warning("All 20 slots are full.")
                else:
                    st.session_state.captured_images[slot] = payload
                    logger.info("Slot Updated (test): slot %s", slot + 1)
                    logger.info("Session State Updated (test): filled=%s", filled_count())
                    st.success(f"Test image added to slot {slot + 1}")
                    st.rerun()

if st.session_state.save_success:
    saved = st.session_state.save_success
    st.success("Student Dataset Saved Successfully")
    detail = st.columns(4)
    detail[0].metric("Student ID", saved["student_id"])
    detail[1].metric("Images Saved", saved["image_count"])
    detail[2].metric("Session ID", saved["session_id"][:12] + "...")
    detail[3].metric("Capture Time", saved["capture_time"])

if st.session_state.cooldown_until is not None:

    @st.fragment(run_every=0.25)
    def cooldown() -> None:
        seconds = max(0, int(st.session_state.cooldown_until - time.time() + 0.99))
        if seconds > 0:
            st.info(f"Preparing Next Student - {seconds}")
        if time.time() >= deadline:
            finalize_session()
        if seconds <= 0:
            st.session_state.cooldown_until = None
            reset_capture_state(context.video_processor)
            st.rerun()

    cooldown()
else:
    if st.button("Keep All Images", type="primary", use_container_width=True):
        count = filled_count()
        if count < TARGET_IMAGES:
            st.error(f"{TARGET_IMAGES} images required before saving. Currently captured: {count}.")
        else:
            try:
                frames = [entry["image"] for entry in st.session_state.captured_images]
                capture_times = [entry["capture_time"] for entry in st.session_state.captured_images]
                student_id, _ = get_attendance_service().save_student_dataset(
                    session_id=session_id,
                    frames=frames,
                    capture_times=capture_times,
                )
                st.session_state.students_collected += 1
                st.session_state.save_success = {
                    "student_id": student_id,
                    "image_count": TARGET_IMAGES,
                    "session_id": session_id,
                    "capture_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                }
                st.session_state.cooldown_until = time.time() + 2
                if context.video_processor:
                    context.video_processor.pause_capture()
                st.rerun()
            except Exception as exc:
                logger.exception("Save workflow failed")
                st.error(f"Could not save student dataset: {exc}")

st.divider()
if st.button("End Session Early", use_container_width=True):
    if context.video_processor:
        context.video_processor.pause_capture()
    finalize_session(status="completed")

if st.session_state.pending_rerun:
    st.session_state.pending_rerun = False
    st.rerun()
elif camera_should_run and context.state.playing and st.session_state.cooldown_until is None:
    time.sleep(0.5)
    st.rerun()
