import streamlit as st
from streamlit_webrtc import webrtc_streamer, VideoProcessorBase, RTCConfiguration
import av
import cv2
import time
import threading

st.set_page_config(page_title="Face Counter", layout="wide")

# 1. Initialize session state for our 20 image slots
if "captured_images" not in st.session_state:
    st.session_state.captured_images = [None] * 20

st.title("📷 Real-Time Face Detection & Auto-Capture")

RTC_CONFIGURATION = RTCConfiguration(
    {"iceServers": [{"urls": ["stun:stun.l.google.com:19302"]}]}
)

class FaceDetector(VideoProcessorBase):
    def __init__(self):
        self.face_cascade = cv2.CascadeClassifier(
            cv2.data.haarcascades + "haarcascade_frontalface_default.xml"
        )
        self.lock = threading.Lock()
        self.frame_buffer = []
        self.last_capture_time = 0

    def recv(self, frame):
        img = frame.to_ndarray(format="bgr24")
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(50, 50)
        )
        face_count = len(faces)

        # 2. Auto-Capture Logic (Only triggers if exactly 1 face is detected)
        if face_count == 1:
            current_time = time.time()
            with self.lock:
                # 1-second cooldown to ensure varied data samples
                if current_time - self.last_capture_time > 1.0:
                    self.frame_buffer.append(img.copy())
                    self.last_capture_time = current_time

        # Draw annotations on the live feed
        for (x, y, w, h) in faces:
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

        cv2.putText(
            img, f"Faces Detected: {face_count}", (20, 40),
            cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2
        )

        return av.VideoFrame.from_ndarray(img, format="bgr24")

# Initialize the WebRTC Streamer
ctx = webrtc_streamer(
    key="face-detector",
    rtc_configuration=RTC_CONFIGURATION,
    video_processor_factory=FaceDetector,
    media_stream_constraints={"video": True, "audio": False},
)

# 3. Process captured frames from the WebRTC background thread
if ctx.state.playing and ctx.video_processor:
    with ctx.video_processor.lock:
        while ctx.video_processor.frame_buffer:
            new_img = ctx.video_processor.frame_buffer.pop(0)
            
            # FIX: Safely find the first empty slot using 'is None' instead of .index()
            empty_idx = next((i for i, v in enumerate(st.session_state.captured_images) if v is None), -1)
            
            if empty_idx != -1:
                st.session_state.captured_images[empty_idx] = new_img
            else:
                # Array is full; clear excess buffers
                ctx.video_processor.frame_buffer.clear()
                break

st.divider()
st.subheader("🖼️ Capture Gallery (20 Slots)")

# 4. Display the 20 placeholders in a responsive grid
cols = st.columns(4)
for i in range(20):
    with cols[i % 4]:
        img_data = st.session_state.captured_images[i]
        
        if img_data is not None:
            # Streamlit requires RGB color space
            img_rgb = cv2.cvtColor(img_data, cv2.COLOR_BGR2RGB)
            st.image(img_rgb, channels="RGB", caption=f"Sample {i+1}")
            
            # Keep and Reject individual options
            c1, c2 = st.columns(2)
            if c1.button("Keep", key=f"keep_{i}", use_container_width=True):
                st.info(f"Keep logic for Sample {i+1} will be implemented in future.")
                
            if c2.button("Reject", key=f"reject_{i}", use_container_width=True):
                # Clear this specific slot so the auto-capture loop can overwrite it
                st.session_state.captured_images[i] = None
                st.rerun()
        else:
            # Empty Placeholder UI
            st.markdown(
                f"""
                <div style='border: 2px dashed gray; border-radius: 5px; height: 180px; 
                display: flex; align-items: center; justify-content: center; color: gray;'>
                Slot {i+1}<br>Waiting for 1 face...
                </div>
                <br>
                """,
                unsafe_allow_html=True
            )

st.divider()

# 5. Global Actions
c_keep_all, c_reject_all, _ = st.columns([1, 1, 2])
with c_keep_all:
    if st.button("Keep All", type="primary", use_container_width=True):
        st.success("Keep All logic will be implemented in future.")
        
with c_reject_all:
    if st.button("Reject All", use_container_width=True):
        st.session_state.captured_images = [None] * 20
        st.rerun()

# 6. UI Auto-Refresh Polling
# FIX: Safely check if any slot is None without triggering NumPy truth value ambiguity
if ctx.state.playing and any(img is None for img in st.session_state.captured_images):
    time.sleep(1.5)
    st.rerun()