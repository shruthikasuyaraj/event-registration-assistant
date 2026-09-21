import os

from app.event_db import EventDb
from app.memory import RunStore

AGENT_DB = os.environ.get("AGENT_DB", "agent.db")
EVENT_DB = os.environ.get("EVENT_DB", "event.db")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")


def open_stores() -> tuple[RunStore, EventDb]:
    store, db = RunStore(AGENT_DB), EventDb(EVENT_DB)
    store.migrate()
    db.migrate()
    return store, db


def make_providers(mock: bool, slow: float = 0.0) -> dict:
    """One provider per agent. With Gemini all three share one client; each keeps its own prompt and tools."""
    if mock:
        from app.providers import demo_providers

        return demo_providers(slow)
    from app.providers import GeminiProvider

    gemini = GeminiProvider(GEMINI_MODEL)
    return {"supervisor": gemini, "event_info": gemini, "registration": gemini}
