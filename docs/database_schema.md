# Database Schema Documentation

## `students`

- `roll_no` primary key
- `name`
- `dept`
- `sem`

## `student_images`

- `image_id` primary key
- `roll_no` foreign key to `students.roll_no`
- `image_path`
- `uploaded_at`

## `attendance_sessions`

- `session_id` primary key
- `prof_name`
- `course_name`
- `start_time`
- `end_time`
- `expected_students`
- `captured_students`
- `status` values: `ACTIVE`, `CLOSED`

## `attendance_captures`

- `capture_id` primary key
- `session_id` foreign key to `attendance_sessions.session_id`
- `image_path`
- `capture_time`

## `attendance_records`

- `record_id` primary key
- `session_id` foreign key to `attendance_sessions.session_id`
- `roll_no` foreign key to `students.roll_no`
- `confidence_score` constrained to `0..1`
- `marked_at`
- `status` values: `PRESENT`, `ABSENT`, `MANUALLY_VERIFIED`

## Storage Layout

- `student-images/<roll_no>/img1.jpg`
- `attendance-sessions/<session_id>/capture_1.jpg`

## Integrity Rules

- `roll_no` must exist before adding student images.
- `session_id` must exist before adding captures or attendance records.
- `image_path` is required.
- Duplicate attendance records for the same `(session_id, roll_no)` are rejected.
