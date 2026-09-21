# Event Registration Assistant

A campus event registration agent. Ask about events, check eligibility, register participants, join waitlists.

## Run

```powershell
# Terminal UI
python -m app.ui

# Demo (no API key needed)
python -m scripts.demo
python -m scripts.demo --crash

# Worker
python -m scripts.worker --mock

# Tests
pytest
```

## How to use the UI

1. Run `python -m app.ui`
2. Enter a participant ID (try `22CS045`)
3. Enter a question (try `Is the AI & Data Science Meetup available?`)
4. Type `quit` to exit
