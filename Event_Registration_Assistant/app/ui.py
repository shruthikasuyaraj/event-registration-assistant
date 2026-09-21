"""Simple terminal UI for the event registration assistant.

Run: python -m app.ui
"""

from app.config import open_stores, make_providers
from app.worker import Worker


def main():
    store, db = open_stores()
    providers = make_providers(mock=True)
    print("=" * 50)
    print("  Event Registration Assistant")
    print("=" * 50)
    print("Enter a participant ID and a question.")
    print("Type 'quit' to exit.\n")

    while True:
        try:
            participant_id = input("Participant ID: ").strip()
            if not participant_id:
                continue
            if participant_id.lower() == "quit":
                break
            question = input("Question: ").strip()
            if not question:
                continue
            if question.lower() == "quit":
                break
        except (EOFError, KeyboardInterrupt):
            break

        thread = store.create_thread(participant_id)
        run_id = store.enqueue(thread, question, "mock")
        Worker(store, db, providers, worker_id="ui-worker").run_until_idle()
        run = store.get_run(run_id)
        history = store.load_history(thread)
        reply = (
            history[-1]["text"]
            if run and run["status"] == "succeeded"
            else (run["error_code"] if run else "no run")
        )
        print(f"\n  Assistant: {reply}\n")

    print("\nGoodbye!")


if __name__ == "__main__":
    main()
