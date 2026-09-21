import inspect
import pytest
from app.tools.event_tools import EventCatalogueTools,RegistrationTools
@pytest.mark.parametrize("cls", [EventCatalogueTools,RegistrationTools])
def test_every_tool_is_described(cls):
    # both classes need a bound object for introspection
    for name in cls.TOOL_NAMES: assert len(inspect.getdoc(getattr(cls,name)) or "")>=120,name
def test_event_search(db):
    r=EventCatalogueTools(db,"22CS045").list_events("AI")
    assert r["events"][0]["event_id"]==1 and r["events"][0]["seats_available"]==2
def test_eligibility_is_from_database(db):
    tools=EventCatalogueTools(db,"22EC031")
    assert tools.check_eligibility(1)["eligible"] is False
    db.conn.execute("UPDATE eligibility_rule SET dept=NULL WHERE event_id=1")
    assert tools.check_eligibility(1)["eligible"] is True
def test_policy_comes_from_database(db):
    tools=RegistrationTools(db,"22CS099")
    assert tools.check_registration_limit()["can_register"] is False
    db.conn.execute("UPDATE policy SET value=3 WHERE name='max_active_registrations'")
    assert tools.check_registration_limit()["can_register"] is True
def test_register_requires_eligibility(db):
    r=RegistrationTools(db,"22EC031").register(1)
    assert r["error"]=="ineligible" and db.count("registration")==2
def test_register_consumes_last_seat(db):
    # event 1 has two seats; the seed has none taken
    t=RegistrationTools(db,"22CS045")
    assert t.register(1)["status"]=="registered"
    assert db.get_event(1)["seats_available"]==1
def test_second_student_gets_full(db):
    assert RegistrationTools(db,"22CS045").register(1)["status"]=="registered"
    db.conn.execute("UPDATE policy SET value=3 WHERE name='max_active_registrations'")
    assert RegistrationTools(db,"22CS099").register(1)["status"]=="registered"
    db.conn.execute("UPDATE event SET seats_available=0 WHERE id=1")
    assert RegistrationTools(db,"22IT017").register(1)["error"]=="full"

def test_register_repeat_is_safe(db):
    t=RegistrationTools(db,"22CS045")
    assert t.register(1)["status"]=="registered"
    assert t.register(1)["status"]=="already_registered"
    assert db.count("registration")==3
def test_waitlist_full_event(db):
    t=RegistrationTools(db,"22CS045")
    r=t.join_waitlist(2)
    assert r["status"]=="waitlisted"
    assert t.join_waitlist(2)["status"]=="already_waitlisted"
def test_waitlist_rejects_when_seat_available(db):
    assert RegistrationTools(db,"22CS045").join_waitlist(1)["error"]=="seats_available"
def test_notification_dedupes(db):
    t=RegistrationTools(db,"22CS045")
    a=t.notify_student("Registration confirmed.")
    b=t.notify_student("Registration confirmed.")
    assert a["notification_id"]==b["notification_id"] and b["duplicate"] is True
def test_tools_cannot_change_bound_student():
    params={n:list(inspect.signature(getattr(RegistrationTools,n)).parameters) for n in RegistrationTools.TOOL_NAMES}
    assert all("student_id" not in p for p in params.values())
