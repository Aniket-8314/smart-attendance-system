"""Create an attendance session."""

import logging
import os
import sys

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
    "Create a live attendance session for a course and professor.",
)

service = AttendanceService()

with st.form("create_attendance_session", clear_on_submit=False):
    st.subheader("Session Setup")
    prof_name = st.text_input(
        "Professor Name",
        placeholder="Professor Sharma",
        max_chars=120,
    )
    course_name = st.text_input(
        "Course Name",
        placeholder="Computer Networks",
        max_chars=160,
    )
    expected_students = st.number_input(
        "Expected Students",
        min_value=0,
        step=1,
        value=0,
        help="Optional planning value used for session metrics.",
    )
    submitted = st.form_submit_button(
        "Start Attendance Session",
        type="primary",
        use_container_width=True,
    )

if submitted:
    try:
        session = service.create_session(
            prof_name=prof_name,
            course_name=course_name,
            expected_students=int(expected_students) or None,
        )
        st.session_state.current_session_id = session.session_id
        st.session_state.current_prof_name = session.prof_name
        st.session_state.current_course_name = session.course_name
        st.session_state.session_finalized = False
        st.session_state.captured_images = []
        st.session_state.pending_attendance = []
        st.switch_page("pages/attendance_session.py")
    except Exception as exc:
        st.error(f"Could not start session: {exc}")

st.markdown(
    """
    <div class="info-panel">
      <strong>Workflow:</strong> open a session, capture classroom images, then close the session once attendance is complete.
    </div>
    """,
    unsafe_allow_html=True,
)
