# Campus Event Registration Assistant

A small end-to-end agent service inspired by the supplied Campus Library Assistant, but implemented for **event registration**.

A student asks a question in plain English. A **supervisor** delegates to:
- an **events specialist** — read-only: finds events and checks eligibility;
- a **registration specialist** — can inspect the student's registrations, register, join a waitlist, and record notifications, but is bound to the current student.

```text
student
   │
   ▼
queue (agent.db)
   │
   ▼
worker ──▶ supervisor
             │
             ├── ask_events ─────▶ events specialist
             │                       ├── list_events
             │                       └── check_eligibility
             │
             └── ask_registration ─▶ registration specialist
                                      ├── get_student
                                      ├── check_registration_limit
                                      ├── register *
                                      ├── join_waitlist *
                                      └── notify_student *
                                      * side effects: once per idempotency key
```

### Terminal UI

```powershell
python -m app.ui
```

Follow the prompts: enter a student ID and a question. Type `quit` to exit.

## Run it — no API key needed

### Windows

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

python -m scripts.demo
python -m scripts.demo --crash
pytest
```

`python -m scripts.demo` runs two deterministic conversations. `python -m scripts.demo --crash` simulates a worker dying immediately after a registration is committed; a second worker resumes the run and the registration is not duplicated.

## Real Gemini

Set the key in the current terminal session:

```powershell
$env:GEMINI_API_KEY="your-key"
python -m scripts.demo --real
```

Or on Windows CMD:

```cmd
set GEMINI_API_KEY=your-key
python -m scripts.demo --real
```

For a persistent user-level environment variable, use Windows Environment Variables or `setx GEMINI_API_KEY "your-key"`; restart the terminal afterwards.

The project defaults to `gemini-2.5-flash`. You can override it with `GEMINI_MODEL`.

## Interactive worker

Terminal 1:

```bash
python -m scripts.worker
```

Terminal 2:

```bash
python -m scripts.ask --student 22CS045 "Find AI events and register me if I am eligible."
```

## Seed data

| Student | Dept | Year | Notes |
|---|---|---:|---|
| 22CS045 Priya Raman | CSE | 2 | Can register |
| 22IT017 Arjun Kumar | IT | 2 | Can register for general eligible events |
| 22EC031 Divya Sekar | ECE | 3 | Not eligible for the CSE/IT workshop |
| 22CS099 Kavin Raj | CSE | 3 | Already has one registration |

Events include:
- **AI & Backend Engineering Workshop** — CSE/IT, 2–4 years, 2 seats.
- **Cloud Career Talk** — all departments, 2–4 years, 1 seat.
- **Competitive Programming Sprint** — all departments, 2–4 years, 3 seats.
- **ECE Embedded Systems Meetup** — ECE, 2–4 years, 2 seats.

The Cloud Career Talk is seeded full so the scripted route exercises the waitlist behavior directly.

## Where the durable-agent ideas appear

| Concept | Where |
|---|---|
| Agent memory separate from business data | `agent.db` vs `event.db` |
| Tool descriptions as model guidance | `app/tools/event_tools.py` |
| Business rules in data | `schema/event.sql` + `EventDb.is_eligible()` |
| Queue / lease / heartbeat / reaper | `app/memory.py`, `app/worker.py`, `app/runner.py` |
| Idempotency | `app/idempotency.py`, `EventDb.once()` |
| Safe seat allocation | `EventDb.register()` with `version` + `seats_available > 0` |
| Supervisor → specialist delegation | `app/agents.py` |
| Least privilege | events specialist has no write tools |
| Bound identity | registration tools receive `student_id` from the server, not the model |
| Crash replay | `scripts/demo.py --crash`, `tests/test_end_to_end.py` |
| Retry / dead-letter | inherited durable execution in `RunStore.fail_attempt()` |

## Important design choices

### 1. Two databases

`event.db` is the source of truth for event-domain data. `agent.db` is the durable execution store. Keeping them separate prevents the agent's conversation/queue concerns from becoming business data.

### 2. Eligibility is enforced twice

The read-only specialist can explain eligibility before an action. More importantly, `register()` checks eligibility again itself. A model cannot bypass the rule by directly calling the write tool.

### 3. Seat clashes are handled in the database

`register()` updates a seat only when `seats_available > 0` and the stored `version` still matches. A concurrent/lost race becomes a normal `full` result rather than creating a negative seat count.

### 4. Side effects are explicit

`register`, `join_waitlist`, and `notify_student` are marked as side effects. The supervisor cannot call them directly; it delegates to the registration specialist. `db.once()` stores the result with the idempotency key in the same transaction.

### 5. Least privilege

The events specialist cannot register or waitlist anyone. The registration specialist is constructed with one server-bound `student_id`; the model has no tool argument that lets it choose another student.

## Known limits

- Specialist inner steps are not checkpointed individually; the delegation is recorded by the supervisor run. On a crash, the specialist may execute again, while idempotency protects its side effects.
- Idempotency keys assume a repeated model call has the same tool name and arguments. The deterministic scripted provider guarantees this for the demo.
- There is no human approval step before registration; that can be added as a later workflow feature.
- Notification is represented by a database record rather than a real SMS/email provider.
