import inspect,pytest
from app.tools.event_tools import EventInfoTools,RegistrationTools
@pytest.mark.parametrize("cls",[EventInfoTools,RegistrationTools])
def test_every_tool_is_described(cls):
    for name in cls.TOOL_NAMES: assert len(inspect.getdoc(getattr(cls,name)) or "")>=120
def test_search_events(db):
    result=EventInfoTools(db).search_events("AI & Data Science")["events"]
    assert result[0]["id"]==1 and result[0]["seats_available"]==2
def test_empty_search(db): assert EventInfoTools(db).search_events(" ")["error"]=="empty_query"
def test_policy_comes_from_data(db):
    tools=RegistrationTools(db,"22IT017")
    assert tools.check_eligibility(2)["eligible"] is True
    db.conn.execute("UPDATE policy SET value=0 WHERE name='max_event_registrations'")
    assert tools.check_eligibility(2)["eligible"] is False
def test_department_eligibility(db):
    assert "restricted to IT" in RegistrationTools(db,"22CS045").check_eligibility(2)["reasons"][0]
def test_registration_consumes_seat(db):
    tools=RegistrationTools(db,"22CS045")
    assert tools.register_event(1)["status"]=="registered"
    assert db.get_event(1)["seats_available"]==1
def test_repeating_registration_is_safe(db):
    tools=RegistrationTools(db,"22CS045")
    assert tools.register_event(1)["status"]=="registered"
    assert tools.register_event(1)["status"]=="already_registered"
    assert db.get_event(1)["seats_available"]==1
def test_full_event_can_be_waitlisted(db):
    tools=RegistrationTools(db,"22IT017")
    db.conn.execute("UPDATE event SET seats_available=0 WHERE id=1")
    assert tools.join_waitlist(1)["status"]=="waitlisted"
def test_waitlist_refuses_when_seat_exists(db):
    assert RegistrationTools(db,"22CS045").join_waitlist(1)["error"]=="seats_available"
def test_registration_limit_is_enforced(db):
    tools=RegistrationTools(db,"22CS045")
    tools.register_event(1);tools.register_event(3)
    assert tools.register_event(2)["error"]=="not_allowed"
def test_notification_is_deduplicated(db):
    tools=RegistrationTools(db,"22CS045")
    a=tools.notify_participant("Registered.");b=tools.notify_participant("Registered.")
    assert a["notification_id"]==b["notification_id"] and b["duplicate"] is True
def test_read_only_specialist_has_no_writes(db):
    assert set(EventInfoTools.TOOL_NAMES)=={"search_events","get_event"}
    assert not EventInfoTools.SIDE_EFFECTS
def test_registration_tool_has_side_effects(db):
    assert {"register_event","join_waitlist","notify_participant"}<=set(RegistrationTools.SIDE_EFFECTS)
def test_participant_cannot_be_switched_by_tool_args(db):
    params={n:list(inspect.signature(getattr(RegistrationTools,n)).parameters) for n in RegistrationTools.TOOL_NAMES}
    assert all("participant_id" not in p for p in params.values())
