import pytest
from app.providers import demo_providers
from app.worker import Worker
from tests.conftest import SimulatedCrash
def ask(store,participant_id,text):
    thread=store.create_thread(participant_id);return thread,store.enqueue(thread,text,"mock")
def test_question_goes_end_to_end(store,db):
    thread,run_id=ask(store,"22CS045","Is AI & Data Science Meetup available? If it is, register me and send a confirmation.")
    assert Worker(store,db,demo_providers(),worker_id="w").run_until_idle()==[(run_id,"succeeded")]
    assert "registered" in store.load_history(thread)[-1]["text"].lower()
    assert db.count("registration")==2 and db.count("notification")==1
def test_restricted_event_is_normal_answer(store,db):
    thread,run_id=ask(store,"22CS045","Can I register for the Cloud Computing Workshop?")
    Worker(store,db,demo_providers(),worker_id="w").run_until_idle()
    assert store.get_run(run_id)["status"]=="succeeded"
    assert "restricted" in store.load_history(thread)[-1]["text"]
    assert db.count("notification")==0
def test_crash_after_registration_replays_without_duplicate(store,db,clock):
    _,run_id=ask(store,"22CS045","Is AI & Data Science Meetup available? If it is, register me and send a confirmation.")
    real_once=db.once
    def once_then_die(key,tool_name,effect):
        result=real_once(key,tool_name,effect)
        if tool_name=="register_event":raise SimulatedCrash()
        return result
    db.once=once_then_die
    with pytest.raises(SimulatedCrash):Worker(store,db,demo_providers(),worker_id="A",lease_seconds=30).run_once()
    db.once=real_once;assert db.count("registration")==2 and store.get_run(run_id)["status"]=="running"
    clock.advance(31)
    assert Worker(store,db,demo_providers(),worker_id="B",lease_seconds=30).run_until_idle()==[(run_id,"succeeded")]
    assert db.count("registration")==2 and db.count("notification")==1 and store.get_run(run_id)["attempts"]==2
def test_asking_twice_keeps_registration_safe(store,db):
    for _ in range(2):ask(store,"22CS045","Is AI & Data Science Meetup available? If it is, register me and send a confirmation.")
    Worker(store,db,demo_providers(),worker_id="w").run_until_idle()
    assert db.count("registration")==2 and db.count("notification")==1
