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
from database.models import Student
from frontend.ui import apply_global_styles, page_header, section_title

MAX_IMAGES = 20

st.set_page_config(
    page_title="Dataset Collection",
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
selected_key = st.selectbox("Select Student", list(student_map.keys()))
selected_student = student_map[selected_key]

roll_no = str(selected_student.roll_no)
save_dir = os.path.join(ROOT_DIR, "dataset", roll_no)
os.makedirs(save_dir, exist_ok=True)

images = sorted(glob.glob(os.path.join(save_dir, "*.jpg")))
existing = len(images)
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
    filename = os.path.join(save_dir, f"img_{existing + 1}.jpg")
    cv2.imwrite(filename, image)
    st.success(f"Image {existing + 1}/{MAX_IMAGES} saved.")
    st.rerun()

section_title("Dataset Controls")
control_col, _ = st.columns([1, 3])
with control_col:
    if st.button("Delete Last Image", use_container_width=True):
        image_paths = glob.glob(os.path.join(save_dir, "*.jpg"))
        ordered_images = sorted(
            image_paths,
            key=lambda path: int(os.path.basename(path).split("_")[1].split(".")[0]),
        )
        if ordered_images:
            os.remove(ordered_images[-1])
            st.success("Last image deleted.")
            st.rerun()

image_paths = glob.glob(os.path.join(save_dir, "*.jpg"))
images = sorted(
    image_paths,
    key=lambda path: int(os.path.basename(path).split("_")[1].split(".")[0]),
)

if images:
    section_title("Dataset Preview")
    cols = st.columns(4)
    for idx, img_path in enumerate(images):
        cols[idx % 4].image(
            img_path,
            caption=os.path.basename(img_path),
            use_container_width=True,
        )

db.close()
