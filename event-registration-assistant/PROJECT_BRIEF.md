# Weekend Project: Event Registration Agent

Build a small end-to-end **Campus Event Registration Assistant** following the same durable-agent patterns as the supplied Library Assistant.

## Domain
A student asks about campus events in plain English. The assistant can discover events, check eligibility, register the student, join a waitlist when an event is full, and record a confirmation notification.

The main clash is the **seat limit**. A business policy also limits how many active registrations a student may hold.

## Requirements covered

1. **Two SQLite databases:** `event.db` contains students/events/registrations; `agent.db` contains threads, messages, runs and queue state.
2. **Five tools:** read-only `list_events`, `check_eligibility`, `get_student`, `check_registration_limit`; side effects `register`, `join_waitlist`, `notify_student`.
3. **Rules in data:** `eligibility_rule` and `policy.max_active_registrations` are database data. `register()` enforces both eligibility and the registration limit even if the model skips the check.
4. **Queue + worker:** a run is queued in `agent.db`, claimed with a lease, heartbeated, and reaped/requeued after worker death.
5. **Idempotency:** side effects use stored idempotency keys. Registration and waitlisting are independently safe to repeat; notifications dedupe by student/message/day.
6. **Multi-agent:** supervisor delegates to an `events` specialist with no write tools and a `registration` specialist bound to one student.
7. **Proof without API key:** scripted providers power `python -m scripts.demo`, `--crash`, and the pytest suite.
8. **Higher-grade feature:** retry/backoff and dead-lettering are inherited from the durable run queue.
