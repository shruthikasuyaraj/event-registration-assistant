from app.agents import SupervisorTools,run_specialist,run_tool
from app.providers import ModelTurn,ScriptedProvider,ToolCall,demo_providers
from app.tools.event_tools import EventCatalogueTools
def test_supervisor_only_has_delegation_tools(db):
    t=SupervisorTools(db,demo_providers(),"22CS045")
    assert set(t.functions())=={"ask_events","ask_registration"}
def test_events_specialist_reads_only(db):
    r,_=run_tool(SupervisorTools(db,demo_providers(),"22CS045"),db,"k1","ask_events",{"question":"Find AI & Backend"})
    assert r["agent"]=="events" and "list_events" in r["tools_used"]
    assert db.count("registration")==2
def test_registration_specialist_can_write_bound_student(db):
    r,_=run_tool(SupervisorTools(db,demo_providers(),"22CS045"),db,"k2","ask_registration",
                 {"request":"Register for event 1 and notify me."})
    assert "register" in r["tools_used"] and db.count("registration")==3
def test_same_delegation_key_does_not_duplicate(db):
    t=SupervisorTools(db,demo_providers(),"22CS045")
    args={"request":"Register for event 1 and notify me."}
    run_tool(t,db,"same", "ask_registration",args); run_tool(t,db,"same","ask_registration",args)
    assert db.count("registration")==3 and db.count("notification")==1
def test_bad_delegation_arguments(db):
    r,_=run_tool(SupervisorTools(db,demo_providers(),"22CS045"),db,"k","ask_registration",{"request":""})
    assert r["error"]=="invalid_arguments"
def test_looping_specialist_stops(db):
    looping=ScriptedProvider([ModelTurn(text=None,tool_calls=[ToolCall("list_events",{"text":"AI"})])],loop=True)
    r=run_specialist("events","sys",EventCatalogueTools(db,"22CS045"),db=db,provider=looping,task="x",parent_key="k")
    assert r["error"]=="specialist_step_limit"
