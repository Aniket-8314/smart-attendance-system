# Smart Attendance System

Python + Streamlit + Supabase attendance tracker with a normalized Postgres schema.

## Database Schema

- `students(roll_no PK, name, dept, sem)`
- `student_images(image_id PK, roll_no FK -> students.roll_no, image_path, uploaded_at)`
- `attendance_sessions(session_id PK, prof_name, course_name, start_time, end_time, expected_students, captured_students, status)`
- `attendance_captures(capture_id PK, session_id FK -> attendance_sessions.session_id, image_path, capture_time)`
- `attendance_records(record_id PK, session_id FK -> attendance_sessions.session_id, roll_no FK -> students.roll_no, confidence_score, marked_at, status)`

## Supabase Storage

- `student-images/<roll_no>/...`
- `attendance-sessions/<session_id>/...`

## Setup

1. Set `DATABASE_URL`, `SUPABASE_URL`, and `SUPABASE_KEY` in `.env`.
2. Run `python migrations/002_migrate_legacy_schema.py` against an existing database, or apply `migrations/001_create_normalized_schema.sql` for a fresh database.
3. Launch the app with your usual Streamlit entrypoint.

## Notes

- Student reference images must exist in `students` before images are added.
- Attendance records are unique per `(session_id, roll_no)`.
- Confidence scores must stay between `0` and `1`.
- The repo does not currently expose a separate FastAPI or Flask API layer; the Streamlit app and backend services are the integration points.
