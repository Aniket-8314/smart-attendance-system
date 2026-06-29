"""Smart Attendance System home page."""

import os
import sys

import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from backend.attendance_service import AttendanceService
from frontend.ui import apply_global_styles, page_header, section_title

st.set_page_config(page_title="IntelMark", page_icon=":mortar_board:", layout="wide")
apply_global_styles()

service = AttendanceService()
students = service.list_students()
sessions = service.list_sessions()
recent_sessions = sessions[:5]

page_header(
    "AI-Powered Attendance System",
    "Register students, upload reference images, start attendance sessions, and review attendance records from one workspace.",
)

student_count = len(students)
session_count = len(sessions)
capture_count = sum(service.get_session_statistics(session.session_id).get("capture_count", 0) for session in sessions)
record_count = sum(service.get_session_statistics(session.session_id).get("record_count", 0) for session in sessions)

metric_col1, metric_col2, metric_col3, metric_col4 = st.columns(4)
metric_col1.metric("Registered Students", student_count)
metric_col2.metric("Attendance Sessions", session_count)
metric_col3.metric("Capture Images", capture_count)
metric_col4.metric("Attendance Records", record_count)

section_title("Actions")
attendance_col, register_col, review_col = st.columns(3)
if attendance_col.button("Start Attendance Session", type="primary", use_container_width=True):
    st.switch_page("pages/start_attendance_session.py")
if register_col.button("Register Student", use_container_width=True):
    st.switch_page("pages/register_student.py")
if review_col.button("Student Registry", use_container_width=True):
    st.switch_page("pages/registry.py")

section_title("Recent Sessions")
if recent_sessions:
    rows = []
    for session in recent_sessions:
        stats = service.get_session_statistics(session.session_id)
        rows.append(
            {
                "session_id": session.session_id,
                "course_name": session.course_name,
                "prof_name": session.prof_name,
                "status": session.status,
                "captures": stats.get("capture_count", 0),
                "records": stats.get("record_count", 0),
                "start_time": session.start_time,
            }
        )
    st.dataframe(rows, use_container_width=True, hide_index=True)
else:
    st.info("No attendance sessions have been created yet.")

