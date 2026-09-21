from app.providers import demo_providers
from app.worker import Worker
from tests.conftest import SimulatedCrash
def ask(store,student,text):
    thread=store.create_thread(student); return thread,store.enqueue(thread,text,"mock")
def test_successful_registration_end_to_end(store,db):
    thread,run=ask(store,"22CS045","Find AI & Backend and register me.")
    assert Worker(store,db,demo_providers(),worker_id="w").run_until_idle()==[(run,"succeeded")]
    assert db.count("registration")==3 and db.count("notification")==1
    assert "registered" in store.load_history(thread)[-1]["text"].lower()
def test_full_event_waitlists_end_to_end(store,db):
    thread,run=ask(store,"22CS045","Find Cloud Career and register me. If full join waitlist.")
    Worker(store,db,demo_providers(),worker_id="w").run_until_idle()
    assert store.get_run(run)["status"]=="succeeded"
    assert db.count("waitlist")==1 and db.count("notification")==1
def test_crash_after_registration_replays_without_duplicate(store,db):
    _,run=ask(store,"22CS045","Find AI & Backend and register me.")
    real_once=db.once
    def once_then_die(key,name,effect):
        result=real_once(key,name,effect)
        if name=="register": raise SimulatedCrash()
        return result
    db.once=once_then_die
    try:
        Worker(store,db,demo_providers(),worker_id="A",lease_seconds=30).run_once()
    except SimulatedCrash:
        pass
    db.once=real_once
    assert db.count("registration")==3 and store.get_run(run)["status"]=="running"
    store.clock=lambda:1790000031.0
    assert Worker(store,db,demo_providers(),worker_id="B",lease_seconds=30).run_until_idle()==[(run,"succeeded")]
    assert db.count("registration")==3 and db.count("notification")==1
def test_two_identical_requests_are_safe(store,db):
    for _ in range(2): ask(store,"22CS045","Find AI & Backend and register me.")
    Worker(store,db,demo_providers(),worker_id="w").run_until_idle()
    assert db.count("registration")==3 and db.count("notification")==1
