import streamlit as st
import numpy as np
import cv2
import os
import glob
import sys

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

sys.path.insert(0, ROOT_DIR)

from database.db import SessionLocal
from database.models import Student

MAX_IMAGES = 20

st.set_page_config(
    page_title="Dataset Collection",
    page_icon="📸",
)

st.title("Dataset Collection")

db = SessionLocal()

students = db.query(Student).all()

if not students:
    st.warning(
        "No students registered. Please register students first."
    )
    st.stop()

student_map = {
    f"{s.roll_no} - {s.name}": s
    for s in students
}

selected_key = st.selectbox(
    "Select Student",
    list(student_map.keys())
)

selected_student = student_map[selected_key]

roll_no = str(selected_student.roll_no)

save_dir = os.path.join(ROOT_DIR,"dataset",roll_no)

os.makedirs(save_dir,exist_ok=True)


st.info(
    f"""
    **Name:** {selected_student.name}

    **Roll No:** {selected_student.roll_no}

    **Department:** {selected_student.department}

    **Semester:** {selected_student.semester}
    """
)


images = sorted(
    glob.glob(
        os.path.join(save_dir, "*.jpg")
    )
)

existing = len(images)

st.metric("Images Collected",f"{existing}/{MAX_IMAGES}")

progress = existing / MAX_IMAGES

st.progress(progress)


if existing >= MAX_IMAGES:

    st.success("Dataset Collection Complete")

    st.balloons()

    st.info("Proceed to Generate Encodings.")

    db.close()

    st.stop()


img_file = st.camera_input("Capture Student Image",width=1000)

if img_file:

    image_bytes = img_file.read()

    image = cv2.imdecode(
        np.frombuffer(
            image_bytes,
            np.uint8
        ),
        cv2.IMREAD_COLOR
    )

    filename = os.path.join(save_dir,f"img_{existing+1}.jpg")

    cv2.imwrite(filename,image)

    st.success(f"Image {existing+1}/{MAX_IMAGES} saved")

    st.rerun()


st.divider()

col1, col2 = st.columns([1, 3])

with col1:

    if st.button("🗑 Delete Last Image"):

        image_paths = glob.glob(os.path.join(save_dir, "*.jpg"))

        images = sorted(
            image_paths,
            key=lambda x: int(os.path.basename(x).split("_")[1].split(".")[0]),
        )

        if images:

            os.remove(images[-1])

            st.success("Last image deleted.")

            st.rerun()

image_paths = glob.glob(os.path.join(save_dir, "*.jpg"))

images = sorted(
    image_paths,
    key=lambda x: int(os.path.basename(x).split("_")[1].split(".")[0]),
)

if images:

    st.divider()

    st.subheader("Dataset Preview")

    cols = st.columns(4)

    for idx, img_path in enumerate(images):

        cols[idx % 4].image(
            img_path,
            caption=os.path.basename(img_path),
            use_container_width=True
        )

db.close()