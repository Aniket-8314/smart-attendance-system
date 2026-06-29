import os
import sys
import time
import cv2
import numpy as np
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from backend.attendance_service import AttendanceService
from frontend.ui import apply_global_styles, page_header, section_title

st.set_page_config(page_title="Register Student", page_icon=":clipboard:", layout="wide")
apply_global_styles(max_width=980)
page_header(
    "Register Student",
    "Create or update a student record by typing their information directly, then capture 20 reference images.",
)

# Initialize face detector (Haar Cascade)
@st.cache_resource
def load_face_detector():
    return cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

face_cascade = load_face_detector()
service = AttendanceService()

# Initialize Session States for Camera Sequence
if "captured_images" not in st.session_state:
    st.session_state["captured_images"] = [None] * 20
if "is_capturing" not in st.session_state:
    st.session_state["is_capturing"] = False
if "retake_index" not in st.session_state:
    st.session_state["retake_index"] = None


with st.form("student_form", clear_on_submit=False):
    left, right = st.columns(2)
    with left:
        # Use the entered roll number as the default value inside the form
        roll_no_value = st.text_input(
            "Roll Number", 
            placeholder="2401ME72", 
            max_chars=8
        )
        name_value = st.text_input(
            "Student Name",  
            placeholder="Full name", 
            max_chars=120
        )
    with right:
        dept_value = st.text_input(
            "Department", 
            placeholder="Computer Science", 
            max_chars=120
        )
        sem_value = st.text_input(
            "Semester", 
            placeholder="5", 
            max_chars=2
        )
    submitted = st.form_submit_button("Save Student", type="primary", use_container_width=True)

if submitted:
    try:
        student = service.create_or_update_student(roll_no=roll_no_value, name=name_value, dept=dept_value, sem=sem_value)
        st.session_state["selected_roll_no"] = student.roll_no
        st.success(f"Saved student {student.roll_no}.")
        st.rerun()
    except Exception as exc:
        st.error(f"Could not save student: {exc}")


if roll_no_value:
    student = service.get_student(roll_no_value)
    if student:
        section_title(f"Capture Reference Images for {student.name} ({student.roll_no})")
        
        # Action Triggers
        col_btn1, col_btn2 = st.columns(2)
        with col_btn1:
            if st.button("Start Camera & Capture Sequence", type="primary", use_container_width=True):
                st.session_state["is_capturing"] = True
                st.session_state["retake_index"] = None
        with col_btn2:
            if st.button("Clear Grid", use_container_width=True):
                st.session_state["captured_images"] = [None] * 20
                st.session_state["is_capturing"] = False
                st.session_state["retake_index"] = None
                st.rerun()

        # Camera Capture Engine Loop
        if st.session_state["is_capturing"] or st.session_state["retake_index"] is not None:
            camera_placeholder = st.empty()
            status_placeholder = st.empty()
            
            cap = cv2.VideoCapture(0)
            
            if not cap.isOpened():
                st.error("Error: Could not access your web camera.")
                st.session_state["is_capturing"] = False
                st.session_state["retake_index"] = None
            else:
                last_capture_time = time.time()
                
                if st.session_state["retake_index"] is not None:
                    target_indices = [st.session_state["retake_index"]]
                    status_placeholder.warning(f"Retaking Image #{st.session_state['retake_index'] + 1}...")
                else:
                    target_indices = [i for i, img in enumerate(st.session_state["captured_images"]) if img is None]
                
                target_idx_iter = iter(target_indices)
                try:
                    current_target = next(target_idx_iter)
                except StopIteration:
                    current_target = None
                
                while cap.isOpened() and current_target is not None:
                    ret, frame = cap.read()
                    if not ret:
                        break
                        
                    frame = cv2.flip(frame, 1)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(100, 100))
                    
                    preview_frame = frame.copy()
                    for (x, y, w, h) in faces:
                        cv2.rectangle(preview_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                    camera_placeholder.image(cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)
                    num_faces = len(faces)
                    current_time = time.time()
                    
                    if num_faces == 1:
                        status_placeholder.success(f"Face detected! Holding target for image #{current_target + 1}...")
                        if current_time - last_capture_time >= 1.0:
                            _, buffer = cv2.imencode('.jpg', frame)
                            img_bytes = buffer.tobytes()
                            
                            st.session_state["captured_images"][current_target] = img_bytes
                            last_capture_time = current_time
                            
                            try:
                                current_target = next(target_idx_iter)
                            except StopIteration:
                                current_target = None
                    elif num_faces == 0:
                        status_placeholder.error("No face detected! Please look directly at the camera.")
                    else:
                        status_placeholder.warning(f"Multiple faces detected ({num_faces})! Ensure only 1 person is visible.")
                        
                    time.sleep(0.03)
                
                cap.release()
                camera_placeholder.empty()
                status_placeholder.empty()
                st.session_state["is_capturing"] = False
                st.session_state["retake_index"] = None
                st.rerun()

        # 20 Image Display Grid Interface
        section_title("Preview Grid (20 Reference Frames)")
        grid_cols = st.columns(4)
        
        for index in range(20):
            with grid_cols[index % 4]:
                st.markdown(f"**Slot #{index + 1}**")
                img_data = st.session_state["captured_images"][index]
                
                if img_data is not None:
                    st.image(img_data, use_container_width=True)
                    if st.button(f"Retake #{index + 1}", key=f"retake_btn_{index}", use_container_width=True):
                        st.session_state["retake_index"] = index
                        st.rerun()
                else:
                    st.info("Empty Frame")

        # Keep All (Submit to Database System Storage)
        all_captured = all(img is not None for img in st.session_state["captured_images"])
        
        if all_captured:
            st.write("---")
            if st.button("Keep All & Save to DB", type="primary", use_container_width=True):
                saved_count = 0
                progress_bar = st.progress(0)
                status_placeholder = st.empty()
                try:
                    # 🔥 NEW: Clear out previous reference images before saving new ones
                    status_placeholder.info("Flushing older reference profile images from repository...")
                    service.delete_student_images(roll_no=student.roll_no)
                    
                    # Upload the new batch of 20 images safely
                    for index, img_bytes in enumerate(st.session_state["captured_images"]):
                        status_placeholder.info(f"Uploading new reference frame {index + 1}/20...")
                        filename = f"capture_{index + 1}_{int(time.time())}.jpg"
                        
                        service.add_student_image(
                            roll_no=student.roll_no,
                            image_bytes=img_bytes,
                            content_type="image/jpeg",
                            filename=filename
                        )
                        saved_count += 1
                        progress_bar.progress(saved_count / 20)
                    
                    status_placeholder.empty()
                    st.success(f"Successfully cleared old profile and saved 20 fresh reference images for {student.name}!")
                    
                    # Flush sequence memory states post successfully updating backend configurations
                    st.session_state["captured_images"] = [None] * 20
                    st.rerun()
                except Exception as exc:
                    status_placeholder.empty()
                    st.error(f"Error persisting frames to your storage database service layers: {exc}")