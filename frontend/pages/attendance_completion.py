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
captures = service.list_session_captures(session_id)
records = service.list_attendance_records(session_id)

if session is None:
    st.error("Session not found in the database.")
    st.stop()

page_header(
    "Attendance Session Complete",
    "Review the session totals and download the capture/attendance report.",
)

first = st.columns(5)
first[0].metric("Professor", session.prof_name)
first[1].metric("Course", session.course_name)
first[2].metric("Session ID", session.session_id[:12] + "...")
first[3].metric("Captures", stats.get("capture_count", 0))
first[4].metric("Attendance Records", stats.get("record_count", 0))

second = st.columns(4)
second[0].metric(
    "Start Time",
    session.start_time.strftime("%Y-%m-%d %H:%M:%S") if session.start_time else "N/A",
)
second[1].metric(
    "End Time",
    session.end_time.strftime("%Y-%m-%d %H:%M:%S") if session.end_time else "N/A",
)
second[2].metric("Expected Students", session.expected_students or 0)
second[3].metric("Captured Students", session.captured_students or 0)

section_title("Attendance Records")
if records:
    st.dataframe(
        [
            {
                "record_id": record.record_id,
                "session_id": record.session_id,
                "roll_no": record.roll_no,
                "confidence_score": record.confidence_score,
                "marked_at": record.marked_at,
                "status": record.status,
            }
            for record in records
        ],
        use_container_width=True,
        hide_index=True,
    )
else:
    st.info("No attendance records were saved for this session.")

report = io.StringIO()
writer = csv.writer(report)
writer.writerow(
    [
        "session_id",
        "prof_name",
        "course_name",
        "capture_id",
        "capture_time",
        "image_path",
    ]
)
for capture in captures:
    writer.writerow(
        [
            session.session_id,
            session.prof_name,
            session.course_name,
            capture.capture_id,
            capture.capture_time.isoformat() if capture.capture_time else "",
            capture.image_path,
        ]
    )


def clear_session() -> None:
    keys = [
        key for key in st.session_state
        if key.startswith("current_")
        or key.startswith("session_")
        or key in {"captured_images", "pending_attendance"}
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
    "Download Capture Report",
    data=report.getvalue(),
    file_name=f"attendance_{session_id}.csv",
    mime="text/csv",
    use_container_width=True,
)
