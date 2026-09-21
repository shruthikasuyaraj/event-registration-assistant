-- event.db: event data. Agent memory/queue stays in agent.db.
CREATE TABLE IF NOT EXISTS participant (
 id INTEGER PRIMARY KEY,
 participant_id TEXT NOT NULL UNIQUE,
 name TEXT NOT NULL,
 dept TEXT NOT NULL,
 role TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS event (
 id INTEGER PRIMARY KEY,
 name TEXT NOT NULL,
 event_date TEXT NOT NULL,
 venue TEXT NOT NULL,
 seat_limit INTEGER NOT NULL,
 seats_available INTEGER NOT NULL CHECK(seats_available>=0),
 eligibility_group TEXT NOT NULL,
 version INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS policy (
 name TEXT PRIMARY KEY,
 value INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS registration (
 id INTEGER PRIMARY KEY,
 participant_id INTEGER NOT NULL REFERENCES participant(id),
 event_id INTEGER NOT NULL REFERENCES event(id),
 status TEXT NOT NULL CHECK(status IN ('registered','waitlisted')),
 created_at REAL NOT NULL,
 UNIQUE(participant_id,event_id)
);
CREATE TABLE IF NOT EXISTS notification (
 id INTEGER PRIMARY KEY,
 participant_id TEXT NOT NULL,
 message TEXT NOT NULL,
 dedupe_key TEXT NOT NULL UNIQUE,
 created_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS idempotency (
 key TEXT PRIMARY KEY,
 tool_name TEXT NOT NULL,
 result TEXT NOT NULL,
 created_at REAL NOT NULL
);
