"""Smart Attendance System home page."""

import os
import sys

import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, ROOT_DIR)

from database.db import SessionLocal, engine
from database.models import Base, Student
from database.schema import initialize_database
from frontend.ui import apply_global_styles, page_header, section_title

initialize_database(engine, Base)

st.set_page_config(page_title="Smart Attendance System", page_icon=":mortar_board:", layout="wide")
apply_global_styles()

page_header(
    "Smart Attendance System",
    "Run timed webcam attendance sessions, register students, and review captured attendance records from one workspace.",
)

with SessionLocal() as db:
    student_count = db.query(Student).count()

metric_col, status_col = st.columns(2)
metric_col.metric("Registered Students", student_count)
status_col.metric("System Status", "Ready")

section_title("Actions")
attendance_col, register_col = st.columns(2)
if attendance_col.button("Start Attendance Collection", type="primary", use_container_width=True):
    st.switch_page("pages/start_attendance_session.py")
if register_col.button("Register Student", use_container_width=True):
    st.switch_page("pages/register_student.py")

section_title("Workflow")
st.markdown(
    """
    <div class="info-panel">
      <strong>Attendance Collection</strong><br>
      Start a timed session, capture 20 validated face images per attendee,
      and store approved captures in the database.
      <br><br>
      <strong>Student Registration</strong><br>
      Add student identity details before using student-linked dataset tools.
    </div>
    """,
    unsafe_allow_html=True,
)
