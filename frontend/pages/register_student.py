import streamlit as st

import sys
import os

ROOT_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..")
)

sys.path.insert(0, ROOT_DIR)

from database.db import SessionLocal,engine
from database.models import Student,Base

Base.metadata.create_all(bind=engine)

st.title("Student Registration")

with st.form("student_form"):

    name = st.text_input("Student Name")

    roll_no = st.text_input("Roll Number")

    department = st.text_input("Department")

    semester = st.selectbox(
        "Semester",
        [
            "1","2","3","4",
            "5","6","7","8"
        ]
    )

    submit = st.form_submit_button(
        "Register Student"
    )

if submit:

    db = SessionLocal()

    try:

        student = Student(
            roll_no=roll_no,
            name=name,
            department=department,
            semester=semester
        )

        db.add(student)
        db.commit()

        st.success(
            f"{name} registered successfully"
        )

    except Exception as e:

        st.error(str(e))

    finally:

        db.close()