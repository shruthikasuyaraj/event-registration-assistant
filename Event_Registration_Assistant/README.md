# Campus Event Registration Assistant

Weekend project adapted from the Campus Library Assistant structure into the **Event Registration** domain. The project keeps agent memory/queue in `agent.db` and event business data in `event.db`.

A participant asks in plain English. A supervisor delegates to:
- **event_info**: read-only specialist for event search and seat information.
- **registration**: participant-bound specialist for eligibility, registration, waitlisting, and notifications.

```text
participant -> agent.db queue -> worker -> supervisor
                                  |-> ask_event_info -> event_info -> search_events, get_event
                                  `-> ask_registration -> registration -> get_participant,
                                                        check_eligibility, register_event*,
                                                        join_waitlist*, notify_participant*
                                                        * side effects use idempotency keys
```

## Requirements covered
1. Two SQLite databases: `agent.db` and `event.db`.
2. Five-plus tools, with descriptions explaining use and side effects.
3. Business rules live in the `policy` table and eligibility is enforced by the tool, not only the prompt.
4. Queue + worker + leases + expired-run replay.
5. Idempotency for registration, waitlisting, and notifications; registration and notification are safe to repeat.
6. Supervisor delegates to two specialists; event_info has no write tools.
7. Scripted models make demo/crash tests work without an API key; 18 tests are included.
8. The crash demo shows a worker dying after registration and a second worker finishing without duplicating the registration.

## Run
```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
pip install -r requirements.txt

python -m scripts.demo
python -m scripts.demo --crash
pytest
```

Optional Gemini:
```bash
set GEMINI_API_KEY=your_key
python -m scripts.demo --real
python -m scripts.worker
python -m scripts.ask --participant 22CS045 "What events are available?"
```

## Seed data
- 22CS045 Priya Raman, CSE
- 22IT017 Arjun Kumar, IT
- 22EC031 Divya Sekar, ECE
- AI & Data Science Meetup: 2 seats
- Cloud Computing Workshop: 1 seat, IT only
- Women in Tech Panel: 3 seats, one seeded registration
- Advanced Robotics Lab: full, ECE only

Policies are stored in `event.db`:
- `max_event_registrations = 2`
- `max_waitlist_entries = 3`

## Architecture choices
`app/db.py`, `app/memory.py`, `app/worker.py`, `app/idempotency.py`, and `app/tools/dispatch.py` retain the generic durable-agent patterns from the library example. The domain-specific pieces were rewritten as `schema/event.sql`, `app/event_db.py`, and `app/tools/event_tools.py`; prompts/delegations and scripted conversations were also rewritten for events.

The assignment brief requires a domain with something that can clash and at least one message. Event registration uses the **seat limit** as the clashing resource and `notify_participant` as the message side effect.