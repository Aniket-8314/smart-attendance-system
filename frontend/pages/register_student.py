"""Student registration page."""

import os
import sys
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from database.db import SessionLocal, engine
from database.models import Base, Student
from database.schema import initialize_database
from frontend.ui import apply_global_styles, page_header

initialize_database(engine, Base)

st.set_page_config(page_title="Register Student", page_icon=":clipboard:", layout="wide")
apply_global_styles(max_width=880)
page_header(
    "Register Student",
    "Create a student record with the identity details used across attendance and dataset workflows.",
)

with st.form("student_form", clear_on_submit=False):
    left, right = st.columns(2)
    with left:
        name = st.text_input("Student Name", placeholder="Full name", max_chars=120)
        roll_no = st.text_input("Roll Number", placeholder="Example: 2401ME01", max_chars=60)
    with right:
        department = st.text_input("Department", placeholder="Example: Computer Science", max_chars=120)
        semester = st.selectbox("Semester", ["1", "2", "3", "4", "5", "6", "7", "8"])

    submit = st.form_submit_button("Register Student", type="primary", use_container_width=True)

if submit:
    cleaned = {
        "name": name.strip(),
        "roll_no": roll_no.strip(),
        "department": department.strip(),
        "semester": semester,
    }
    missing = [label for label, value in cleaned.items() if not value]
    if missing:
        st.error("Please complete every field before registering the student.")
    else:
        db = SessionLocal()
        try:
            student = Student(**cleaned)
            db.add(student)
            db.commit()
            st.session_state["selected_roll_no"] = cleaned["roll_no"]
            st.success(f"{cleaned['name']} registered successfully.")
            st.switch_page("pages/image_capture.py")
        except Exception as exc:
            db.rollback()
            st.error(f"Could not register student: {exc}")
        finally:
            db.close()
