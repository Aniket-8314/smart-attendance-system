CREATE TABLE IF NOT EXISTS students (
    roll_no VARCHAR PRIMARY KEY,
    name VARCHAR NOT NULL,
    dept VARCHAR NOT NULL,
    sem VARCHAR NOT NULL
);

CREATE INDEX IF NOT EXISTS ix_students_roll_no ON students (roll_no);

CREATE TABLE IF NOT EXISTS student_images (
    image_id BIGSERIAL PRIMARY KEY,
    roll_no VARCHAR NOT NULL REFERENCES students (roll_no) ON DELETE CASCADE,
    image_path VARCHAR NOT NULL,
    uploaded_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_student_images_roll_no ON student_images (roll_no);

CREATE TABLE IF NOT EXISTS attendance_sessions (
    session_id VARCHAR PRIMARY KEY,
    prof_name VARCHAR NOT NULL,
    course_name VARCHAR NOT NULL,
    start_time TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    end_time TIMESTAMPTZ NULL,
    expected_students INTEGER NULL,
    captured_students INTEGER NOT NULL DEFAULT 0,
    status VARCHAR NOT NULL DEFAULT 'ACTIVE',
    CONSTRAINT ck_attendance_sessions_status CHECK (status IN ('ACTIVE', 'CLOSED'))
);

CREATE INDEX IF NOT EXISTS ix_attendance_sessions_session_id ON attendance_sessions (session_id);
CREATE INDEX IF NOT EXISTS ix_attendance_sessions_course_name ON attendance_sessions (course_name);

CREATE TABLE IF NOT EXISTS attendance_captures (
    capture_id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES attendance_sessions (session_id) ON DELETE CASCADE,
    image_path VARCHAR NOT NULL,
    capture_time TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS ix_attendance_captures_session_id ON attendance_captures (session_id);

CREATE TABLE IF NOT EXISTS attendance_records (
    record_id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR NOT NULL REFERENCES attendance_sessions (session_id) ON DELETE CASCADE,
    roll_no VARCHAR NOT NULL REFERENCES students (roll_no) ON DELETE CASCADE,
    confidence_score DOUBLE PRECISION NOT NULL,
    marked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    status VARCHAR NOT NULL DEFAULT 'PRESENT',
    CONSTRAINT uq_attendance_records_session_roll UNIQUE (session_id, roll_no),
    CONSTRAINT ck_attendance_records_status CHECK (status IN ('PRESENT', 'ABSENT', 'MANUALLY_VERIFIED')),
    CONSTRAINT ck_attendance_records_confidence_score CHECK (confidence_score >= 0 AND confidence_score <= 1)
);

CREATE INDEX IF NOT EXISTS ix_attendance_records_session_id ON attendance_records (session_id);
CREATE INDEX IF NOT EXISTS ix_attendance_records_roll_no ON attendance_records (roll_no);
