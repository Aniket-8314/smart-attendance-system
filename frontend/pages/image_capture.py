"""Single-student dataset image capture page."""

import glob
import os
import sys

import cv2
import numpy as np
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from database.db import SessionLocal
from database.models import Student,StudentImage
from frontend.ui import apply_global_styles, page_header, section_title

from database.db import supabase,BUCKET_NAME

MAX_IMAGES = 20

st.set_page_config(
    page_title="image capture",
    page_icon=":camera:",
    layout="wide",
)
apply_global_styles()
page_header(
    "Dataset Collection",
    "Capture a 20-image face dataset for a registered student using the browser camera.",
)

db = SessionLocal()
students = db.query(Student).order_by(Student.roll_no).all()

if not students:
    st.warning("No students registered. Please register students first.")
    db.close()
    st.stop()

student_map = {f"{student.roll_no} - {student.name}": student for student in students}
if "selected_roll_no" in st.session_state:
    selected_student = (
        db.query(Student)
        .filter(Student.roll_no == st.session_state["selected_roll_no"])
        .first()
    )
else:
    selected_key = st.selectbox("Select Student", list(student_map.keys()))
    selected_student = student_map[selected_key]

roll_no = str(selected_student.roll_no)
existing = (
    db.query(StudentImage)
    .filter(StudentImage.student_id == selected_student.id)
    .count()
)
progress = existing / MAX_IMAGES

profile_col, progress_col = st.columns([1.2, 1])
with profile_col:
    st.markdown(
        f"""
        <div class="info-panel">
          <strong>Name:</strong> {selected_student.name}<br>
          <strong>Roll No:</strong> {selected_student.roll_no}<br>
          <strong>Department:</strong> {selected_student.department}<br>
          <strong>Semester:</strong> {selected_student.semester}
        </div>
        """,
        unsafe_allow_html=True,
    )
with progress_col:
    st.metric("Images Collected", f"{existing}/{MAX_IMAGES}")
    st.progress(progress)

if existing >= MAX_IMAGES:
    st.success("Dataset collection is complete.")
    st.info("Proceed to Generate Encodings.")
    db.close()
    st.stop()

section_title("Camera Capture")
img_file = st.camera_input("Capture Student Image", width=1000)

if img_file:
    image_bytes = img_file.read()
    image = cv2.imdecode(np.frombuffer(image_bytes, np.uint8), cv2.IMREAD_COLOR)
    _, buffer = cv2.imencode(".jpg", image)

    file_path = f"{roll_no}/img_{existing + 1}.jpg"
    existing = (
        db.query(StudentImage)
        .filter(StudentImage.student_id == selected_student.id)
        .count()
    )
    try:
        supabase.storage.from_(BUCKET_NAME).upload(
            file_path,
            buffer.tobytes()
        )
    except Exception as e:
        st.error(str(e))
        st.stop()

    student_image = StudentImage(
        student_id=selected_student.id,
        image_path=file_path
    )

    db.add(student_image)
    db.commit()

    st.success(f"Image {existing + 1}/{MAX_IMAGES} saved.")
    st.rerun()
images = (
    db.query(StudentImage)
    .filter(StudentImage.student_id == selected_student.id)
    .all()
)

if images:
    section_title("Dataset Preview")

    cols = st.columns(4)

    for idx, image in enumerate(images):

        url = supabase.storage.from_(
            BUCKET_NAME
        ).get_public_url(image.image_path)

        cols[idx % 4].image(
            url,
            caption=os.path.basename(image.image_path),
            use_container_width=True,
        )

db.close()
