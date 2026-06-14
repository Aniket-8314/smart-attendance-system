"""Attendance session completion summary and CSV report."""

import csv
import io
import logging
import os
import sys

import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from backend.attendance_service import AttendanceService
from frontend.ui import apply_global_styles, page_header, section_title

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)

st.set_page_config(page_title="Session Complete", page_icon=":white_check_mark:", layout="wide")
apply_global_styles()

if "current_session_id" not in st.session_state:
    st.error("No completed session is available.")
    if st.button("Return Home"):
        st.switch_page("app.py")
    st.stop()

service = AttendanceService()
session_id = st.session_state.current_session_id
session = service.get_session(session_id)
stats = service.get_session_statistics(session_id)
captures = service.get_session_captures(session_id)

if session is None:
    st.error("Session not found in the database.")
    st.stop()

students_collected = stats.get("total_students_collected", 0)
total_images = stats.get("total_captures", 0)

page_header(
    "Attendance Session Complete",
    "Review the session totals and download the capture report for records or analysis.",
)

first = st.columns(4)
first[0].metric("Instructor Name", session.user_name)
first[1].metric("Session ID", session_id[:12] + "...")
first[2].metric("Students Collected", students_collected)
first[3].metric("Total Images", total_images)

second = st.columns(4)
second[0].metric(
    "Start Time",
    session.session_start.strftime("%Y-%m-%d %H:%M:%S") if session.session_start else "N/A",
)
second[1].metric(
    "End Time",
    session.session_end.strftime("%Y-%m-%d %H:%M:%S") if session.session_end else "N/A",
)
second[2].metric("Duration", f"{session.duration_minutes} minutes")
second[3].metric("Images Per Student", "20" if students_collected else "0")

report = io.StringIO()
writer = csv.writer(report)
writer.writerow([
    "session_id", "student_id", "instructor_name", "capture_timestamp",
    "image_path", "image_width", "image_height", "face_count",
    "verification_status", "capture_number", "device_info", "created_at",
])
for capture in captures:
    writer.writerow([
        session_id,
        capture.cycle_id,
        session.user_name,
        capture.capture_time.isoformat() if capture.capture_time else "",
        capture.image_path,
        capture.image_width,
        capture.image_height,
        capture.face_count,
        capture.verification_status,
        capture.capture_number,
        capture.device_info,
        capture.created_at.isoformat() if capture.created_at else "",
    ])


def clear_session() -> None:
    keys = [
        key for key in st.session_state
        if key.startswith("current_")
        or key.startswith("session_")
        or key in {
            "students_collected",
            "captured_images",
            "retake_slot",
            "cooldown_until",
            "save_success",
        }
    ]
    for key in keys:
        del st.session_state[key]


section_title("Next Steps")
home_col, new_col, report_col = st.columns(3)
if home_col.button("Return Home", use_container_width=True):
    clear_session()
    st.switch_page("app.py")
if new_col.button("Start New Session", type="primary", use_container_width=True):
    clear_session()
    st.switch_page("pages/start_attendance_session.py")
report_col.download_button(
    "Download Session Report",
    data=report.getvalue(),
    file_name=f"attendance_{session_id}.csv",
    mime="text/csv",
    use_container_width=True,
)
