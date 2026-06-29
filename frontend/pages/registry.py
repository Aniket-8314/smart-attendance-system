"""Student registry and image gallery page."""

import os
import sys

import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from backend.attendance_service import AttendanceService
from frontend.ui import apply_global_styles, page_header, section_title

st.set_page_config(page_title="Student Images", page_icon=":camera:", layout="wide")
apply_global_styles(max_width=1120)
page_header(
    "Student Registry",
    "Browse registered students, inspect their reference images, and review image counts from Supabase Storage.",
)

service = AttendanceService()
students = service.list_students()


section_title("All Students")
student_rows = [
    {
        "roll_no": student.roll_no,
        "name": student.name,
        "dept": student.dept,
        "sem": student.sem,
        "images": len(service.list_student_images(student.roll_no)),
    }
    for student in students
]
st.dataframe(student_rows, use_container_width=True, hide_index=True)
