-- event.db: business data. Agent memory and queue live separately in agent.db.
CREATE TABLE IF NOT EXISTS student (
    id INTEGER PRIMARY KEY,
    student_id TEXT NOT NULL UNIQUE,
    name TEXT NOT NULL,
    dept TEXT NOT NULL,
    year INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS event (
    id INTEGER PRIMARY KEY,
    title TEXT NOT NULL,
    description TEXT NOT NULL,
    venue TEXT NOT NULL,
    starts_at TEXT NOT NULL,
    seats_total INTEGER NOT NULL CHECK (seats_total > 0),
    seats_available INTEGER NOT NULL CHECK (seats_available >= 0),
    version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS eligibility_rule (
    id INTEGER PRIMARY KEY,
    event_id INTEGER NOT NULL REFERENCES event(id),
    dept TEXT,
    min_year INTEGER,
    max_year INTEGER,
    UNIQUE(event_id, dept, min_year, max_year)
);
CREATE TABLE IF NOT EXISTS registration (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student(id),
    event_id INTEGER NOT NULL REFERENCES event(id),
    created_at REAL NOT NULL,
    UNIQUE(student_id, event_id)
);
CREATE TABLE IF NOT EXISTS waitlist (
    id INTEGER PRIMARY KEY,
    student_id INTEGER NOT NULL REFERENCES student(id),
    event_id INTEGER NOT NULL REFERENCES event(id),
    created_at REAL NOT NULL,
    UNIQUE(student_id, event_id)
);
CREATE TABLE IF NOT EXISTS notification (
    id INTEGER PRIMARY KEY,
    student_ref TEXT NOT NULL,
    message TEXT NOT NULL,
    dedupe_key TEXT NOT NULL UNIQUE,
    created_at REAL NOT NULL
);
-- Business rules live in data, not prompts.
CREATE TABLE IF NOT EXISTS policy (
    name TEXT PRIMARY KEY,
    value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
    key TEXT PRIMARY KEY,
    tool_name TEXT NOT NULL,
    result TEXT NOT NULL,
    created_at REAL NOT NULL
);
