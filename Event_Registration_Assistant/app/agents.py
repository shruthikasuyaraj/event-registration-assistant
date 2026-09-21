"""Supervisor plus two least-privilege specialists for event registration."""
import time
from collections.abc import Callable
from app.event_db import EventDb
from app.idempotency import idempotency_key
from app.providers import AgentError
from app.tools.event_tools import EventInfoTools,RegistrationTools,Toolset

SPECIALIST_MAX_STEPS=8
SUPERVISOR_SYSTEM="""You are the Campus Event Registration Assistant for participant {participant_id}.
You never search events or change registrations yourself. Delegate:
- ask_event_info for finding events and checking seat availability;
- ask_registration for this participant's account, eligibility, registration, waitlist, and notifications.
Give each specialist a complete request and include event ids once known. Answer briefly using only specialist results."""
EVENT_SYSTEM="""You are the event information specialist. Find events and report event_id, name, date, venue, and seats. You cannot register or waitlist anyone."""
REGISTRATION_SYSTEM="""You are the event registration specialist acting for participant {participant_id} only.
Always call check_eligibility before register_event or join_waitlist. Never invent eligibility rules. After a successful registration or waitlist action, call notify_participant. Report actions briefly."""

def run_tool(toolset:Toolset,db:EventDb,key:str,name:str,args:dict)->tuple[dict,bool]:
    try:
        if name in toolset.DELEGATES:return toolset.delegate(name,args,key),False
        if name in toolset.SIDE_EFFECTS:
            result,fresh=db.once(key,name,lambda:toolset.call(name,args)); return result,not fresh
        return toolset.call(name,args),False
    except AgentError: raise
    except Exception as e:return {"error":"tool_failed","hint":f"{name} failed ({type(e).__name__})."},False

def run_specialist(agent,system,toolset,*,db,provider,task,parent_key,on_step=None):
    contents=[{"role":"user","text":task}]; functions=list(toolset.functions().values()); used=[]; seq=0
    while seq<SPECIALIST_MAX_STEPS:
        turn=provider.generate(system,contents,functions); seq+=1
        if not turn.tool_calls:return {"agent":agent,"answer":turn.text or "","tools_used":used}
        contents.append({"role":"model","text":turn.text,"raw":turn.raw,"tool_calls":[{"name":c.name,"args":c.args} for c in turn.tool_calls]})
        for call in turn.tool_calls:
            seq+=1; key=idempotency_key(parent_key,seq,call.name,call.args); started=time.perf_counter()
            result,replayed=run_tool(toolset,db,key,call.name,call.args); used.append(call.name)
            if on_step:on_step({"agent":agent,"kind":"tool","tool":call.name,"args":call.args,"result":result,"ok":"error" not in result,"replayed":replayed,"ms":round((time.perf_counter()-started)*1000)})
            contents.append({"role":"tool","name":call.name,"result":result})
    return {"agent":agent,"error":"specialist_step_limit","tools_used":used,"hint":"Try a simpler request."}

class SupervisorTools(Toolset):
    TOOL_NAMES=("ask_event_info","ask_registration"); DELEGATES=TOOL_NAMES
    def __init__(self,db,providers,participant_id,on_step=None):self.db,self.providers,self.participant_id,self.on_step=db,providers,participant_id,on_step
    def ask_event_info(self,question:str)->dict:
        """Ask the read-only event specialist to find events or check seats. Use for event discovery and availability. It cannot register anyone."""
        raise RuntimeError("delegations run through delegate()")
    def ask_registration(self,request:str)->dict:
        """Ask the registration specialist to act for the current participant. Use for eligibility, registration, waitlisting, account questions, and confirmations. It can change data."""
        raise RuntimeError("delegations run through delegate()")
    def call_check(self,name,args):
        field="question" if name=="ask_event_info" else "request"
        if set(args)!={field} or not isinstance(args[field],str) or not args[field].strip():return {"error":"invalid_arguments","hint":f"{name} takes one non-empty string: {field}."}
    def delegate(self,name,args,key):
        bad=self.call_check(name,args)
        if bad:return bad
        if self.on_step:self.on_step({"agent":"supervisor","kind":"delegate","tool":name,"args":args})
        if name=="ask_event_info":
            return run_specialist("event_info",EVENT_SYSTEM,EventInfoTools(self.db),db=self.db,provider=self.providers["event_info"],task=args["question"],parent_key=key,on_step=self.on_step)
        return run_specialist("registration",REGISTRATION_SYSTEM.format(participant_id=self.participant_id),RegistrationTools(self.db,self.participant_id),db=self.db,provider=self.providers["registration"],task=args["request"],parent_key=key,on_step=self.on_step)
