import logging
import os
import sys
import time
from datetime import datetime

import cv2
import numpy as np
import streamlit as st

ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
sys.path.insert(0, ROOT_DIR)

from backend.attendance_service import AttendanceService
from frontend.ui import apply_global_styles, page_header, section_title

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

st.set_page_config(page_title="Attendance Session", page_icon=":camera:", layout="wide")
apply_global_styles(max_width=1400)

# Verify Active Session Handshakes
required = ("current_session_id", "current_prof_name", "current_course_name")
if any(key not in st.session_state for key in required):
    st.error("No active attendance session was found.")
    if st.button("Start Attendance Session", type="primary"):
        st.switch_page("pages/start_attendance_session.py")
    st.stop()

# Initialize face detector (Haar Cascade)
@st.cache_resource
def load_face_detector():
    return cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')

face_cascade = load_face_detector()

service = AttendanceService()
session_id = st.session_state.current_session_id
session = service.get_session(session_id)
if session is None:
    st.error("Attendance session not found.")
    st.stop()

# Initialize Session States for 20 Classroom Frame Captures
if "session_captured_images" not in st.session_state:
    st.session_state["session_captured_images"] = [None] * 20
if "session_is_capturing" not in st.session_state:
    st.session_state["session_is_capturing"] = False
if "session_retake_index" not in st.session_state:
    st.session_state["session_retake_index"] = None

page_header(
    "Attendance Session",
    "Course: {session.course_name} | Professor: {session.prof_name}",
)

# Fetch Current System States
stats = service.get_session_statistics(session_id)
captures = service.list_session_captures(session_id)
records = service.list_attendance_records(session_id)
students = service.list_students()

section_title("Session Summary")
summary_cols = st.columns(5)
summary_cols[0].metric("Session ID", session.session_id[:12] + "...")
summary_cols[1].metric("Status", session.status)
summary_cols[2].metric("Captures", stats.get("capture_count", 0))
summary_cols[3].metric("Attendance Records", stats.get("record_count", 0))
summary_cols[4].metric("Captured Students", session.captured_students or 0)

control_col, verify_col = st.columns([1, 1], gap="large")

with control_col:
    section_title("Capture Classroom Reference Grid")
    
    col_btn1, col_btn2 = st.columns(2)
    with col_btn1:
        if st.button("Start Automated Capture Loop", type="primary", use_container_width=True):
            st.session_state["session_is_capturing"] = True
            st.session_state["session_retake_index"] = None
    with col_btn2:
        if st.button("Clear Reference Grid", use_container_width=True):
            st.session_state["session_captured_images"] = [None] * 20
            st.session_state["session_is_capturing"] = False
            st.session_state["session_retake_index"] = None
            st.rerun()

    # Camera Capture Framework Loop
    if st.session_state["session_is_capturing"] or st.session_state["session_retake_index"] is not None:
        camera_placeholder = st.empty()
        status_placeholder = st.empty()
        
        cap = cv2.VideoCapture(0)
        
        if not cap.isOpened():
            st.error("Error: Could not access web camera components.")
            st.session_state["session_is_capturing"] = False
            st.session_state["session_retake_index"] = None
        else:
            last_capture_time = time.time()
            
            if st.session_state["session_retake_index"] is not None:
                target_indices = [st.session_state["session_retake_index"]]
                status_placeholder.warning(f"Retaking Sample Frame #{st.session_state['session_retake_index'] + 1}...")
            else:
                target_indices = [i for i, img in enumerate(st.session_state["session_captured_images"]) if img is None]
            
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
                faces = face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(80, 80))
                
                preview_frame = frame.copy()
                for (x, y, w, h) in faces:
                    cv2.rectangle(preview_frame, (x, y), (x+w, y+h), (0, 255, 0), 2)
                    
                camera_placeholder.image(cv2.cvtColor(preview_frame, cv2.COLOR_BGR2RGB), channels="RGB", use_container_width=True)
                
                num_faces = len(faces)
                current_time = time.time()
                
                # Validation requirement matching previous rules
                if num_faces == 1:
                    status_placeholder.success(f"Target locked! Storing reference sequence for Slot #{current_target + 1}...")
                    if current_time - last_capture_time >= 1.0:
                        _, buffer = cv2.imencode('.jpg', frame)
                        img_bytes = buffer.tobytes()
                        
                        st.session_state["session_captured_images"][current_target] = img_bytes
                        last_capture_time = current_time
                        
                        try:
                            current_target = next(target_idx_iter)
                        except StopIteration:
                            current_target = None
                elif num_faces == 0:
                    status_placeholder.error("No face detected inside tracking metrics. Adjust focus.")
                else:
                    status_placeholder.warning(f"Multiple tracking profiles detected ({num_faces}). Keep view clean.")
                    
                time.sleep(0.03)
                
            cap.release()
            camera_placeholder.empty()
            status_placeholder.empty()
            st.session_state["session_is_capturing"] = False
            st.session_state["session_retake_index"] = None
            st.rerun()

    if st.button("Close Active Session", use_container_width=True):
        service.close_session(session_id)
        st.session_state.session_finalized = True
        st.switch_page("pages/attendance_completion.py")

with verify_col:
    section_title("Manual Attendance Marking")
    if students:
        with st.form("attendance_record_form", clear_on_submit=True):
            student_label = st.selectbox(
                "Student",
                [f"{student.roll_no} - {student.name}" for student in students],
            )
            confidence_score = st.slider("Confidence Score", 0.0, 1.0, 0.95, 0.01)
            status_val = st.selectbox(
                "Status",
                ["PRESENT", "ABSENT", "MANUALLY_VERIFIED"],
            )
            submit_record = st.form_submit_button("Save Attendance Record", use_container_width=True)
            
        if submit_record:
            roll_no = student_label.split(" - ", 1)[0]
            try:
                record = service.add_attendance_record(
                    session_id=session_id,
                    roll_no=roll_no,
                    confidence_score=float(confidence_score),
                    status=status_val,
                    marked_at=datetime.now().astimezone(),
                )
                st.success(f"Recorded {record.roll_no} as {record.status}.")
                st.rerun()
            except Exception as exc:
                st.error(f"Could not save attendance record: {exc}")
    else:
        st.info("Register students before marking attendance.")

# 20 Image Display Grid Interface matching structural criteria
section_title("Live Preview Reference Grid (20 Collected Frames)")
grid_cols = st.columns(4)

for index in range(20):
    with grid_cols[index % 4]:
        st.markdown(f"**Sequence Slot #{index + 1}**")
        img_data = st.session_state["session_captured_images"][index]
        
        if img_data is not None:
            st.image(img_data, use_container_width=True)
            if st.button(f"Retake Frame #{index + 1}", key=f"session_retake_btn_{index}", use_container_width=True):
                st.session_state["session_retake_index"] = index
                st.rerun()
        else:
            st.info("Awaiting Capture")

# Keep All Button Trigger Logic at the very end
all_captured = all(img is not None for img in st.session_state["session_captured_images"])

if all_captured:
    st.write("---")
    if st.button("Keep All & Save Captures to DB", type="primary", use_container_width=True):
        saved_count = 0
        progress_bar = st.progress(0)
        try:
            # 1. Save all 20 individual image assets into your Capture backend table
            for index, img_bytes in enumerate(st.session_state["session_captured_images"]):
                capture = service.add_capture(
                    session_id=session_id,
                    image_bytes=img_bytes,
                    capture_time=datetime.now().astimezone(),
                )
                saved_count += 1
                progress_bar.progress(saved_count / 20)
            
            # 2. Increment the loop counter based on current session snapshot values
            current_loops = session.captured_students or 0
            new_loop_count = current_loops + 1
            
            # 3. Commit the structural count increment straight to the Database metadata
            try:
                service.update_session_loop_counter(session_id=session_id, loop_count=new_loop_count)
                st.success(f"Successfully finalized and posted camera execution batch #{new_loop_count} (20 frames)!")
            except AttributeError:
                # Direct fallback alert if backend initialization is pending
                st.warning("Captured image arrays saved, but backend 'update_session_loop_counter' method needs declaration.")
            
            # 4. Flush grid state buffers clean for the next tracking loop iteration
            st.session_state["session_captured_images"] = [None] * 20
            st.rerun()
            
        except Exception as exc:
            st.error(f"Error persisting session frames to database: {exc}")