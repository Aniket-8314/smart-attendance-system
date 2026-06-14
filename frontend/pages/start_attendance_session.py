"""Create an attendance dataset collection session."""

import logging
import os
import sys
import time

import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from backend.attendance_service import AttendanceService
from frontend.ui import apply_global_styles, page_header

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

st.set_page_config(
    page_title="Start Attendance Session",
    page_icon=":camera:",
    layout="wide",
)
apply_global_styles(max_width=980)
page_header(
    "Start Attendance Session",
    "Configure the instructor and session duration before opening the live capture workspace.",
)

service = AttendanceService()

with st.form("create_attendance_session", clear_on_submit=False):
    st.subheader("Session Setup")
    instructor_name = st.text_input(
        "Instructor Name",
        placeholder="Professor Sharma",
        help="Required. Examples: Teacher 1, Professor Sharma, Instructor A.",
        max_chars=100,
    )
    duration_minutes = st.slider(
        "Attendance Duration",
        min_value=1,
        max_value=120,
        value=10,
        format="%d min",
        help="Session length from 1 to 120 minutes.",
    )
    submitted = st.form_submit_button(
        "Start Attendance Session",
        type="primary",
        use_container_width=True,
    )

if submitted:
    if not instructor_name.strip():
        st.error("Instructor Name is required.")
    else:
        try:
            session = service.create_session(
                user_name=instructor_name,
                duration_minutes=duration_minutes,
                collection_type="attendance",
            )
            st.session_state.current_session_id = session.session_id
            st.session_state.current_instructor_name = session.user_name
            st.session_state.session_duration_minutes = duration_minutes
            st.session_state.session_start_epoch = time.time()
            st.session_state.session_deadline_epoch = time.time() + duration_minutes * 60
            st.session_state.students_collected = 0
            st.session_state.captured_images = [None] * 20
            st.session_state.retake_slot = None
            st.session_state.cooldown_until = None
            st.session_state.save_success = None
            st.session_state.session_finalized = False
            st.switch_page("pages/attendance_session.py")
        except Exception as exc:
            st.error(f"Database failure: {exc}")

st.markdown(
    """
    <div class="info-panel">
      <strong>Capture rule:</strong> the camera captures only when exactly one face is visible.
      Each attendee needs 20 accepted images before the set can be saved.
      Retake replaces the same slot instead of creating a new card.
    </div>
    """,
    unsafe_allow_html=True,
)
