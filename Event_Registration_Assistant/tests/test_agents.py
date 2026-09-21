from app.agents import SupervisorTools,run_specialist,run_tool
from app.providers import ModelTurn,ScriptedProvider,ToolCall,demo_providers
from app.tools.event_tools import EventInfoTools
def test_supervisor_only_delegates(db):
    tools=SupervisorTools(db,demo_providers(),"22CS045")
    assert set(tools.functions())=={"ask_event_info","ask_registration"}
def test_event_specialist_is_read_only(db):
    result,_=run_tool(SupervisorTools(db,demo_providers(),"22CS045"),db,"k","ask_event_info",{"question":"Find AI & Data Science"})
    assert result["agent"]=="event_info" and result["tools_used"]==["search_events"]
def test_registration_specialist_registers(db):
    result,_=run_tool(SupervisorTools(db,demo_providers(),"22CS045"),db,"k","ask_registration",{"request":"Register participant for event 1 and send a confirmation."})
    assert "register_event" in result["tools_used"] and db.count("notification")==1
def test_repeated_delegation_with_same_key_is_safe(db):
    tools=SupervisorTools(db,demo_providers(),"22CS045");args={"request":"Register participant for event 1 and send a confirmation."}
    run_tool(tools,db,"same-key","ask_registration",args);run_tool(tools,db,"same-key","ask_registration",args)
    assert db.count("registration")==2 and db.count("notification")==1
def test_bad_delegation_arguments(db):
    result,_=run_tool(SupervisorTools(db,demo_providers(),"22CS045"),db,"k","ask_registration",{"request":""})
    assert result["error"]=="invalid_arguments"
def test_looping_specialist_stops(db):
    looping=ScriptedProvider([ModelTurn(text=None,tool_calls=[ToolCall("search_events",{"text":"AI"})])],loop=True)
    result=run_specialist("event_info","sys",EventInfoTools(db),db=db,provider=looping,task="x",parent_key="k")
    assert result["error"]=="specialist_step_limit"
def test_specialists_receive_only_their_task(db):
    providers=demo_providers()
    run_tool(SupervisorTools(db,providers,"22CS045"),db,"k","ask_event_info",{"question":"Find AI & Data Science"})
    assert providers["event_info"].calls[0]==[{"role":"user","text":"Find AI & Data Science"}]
    assert providers["registration"].calls==[]
