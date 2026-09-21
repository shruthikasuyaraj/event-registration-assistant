"""Day 4: supervisor delegates to a read-only event specialist and a registration specialist."""
import time
from collections.abc import Callable
from app.idempotency import idempotency_key
from app.event_db import EventDb
from app.providers import AgentError
from app.tools.event_tools import EventCatalogueTools, RegistrationTools, Toolset

SPECIALIST_MAX_STEPS=10
SUPERVISOR_SYSTEM="""You are the Campus Event Registration Assistant for student {student_id}.
You never query event data or change registrations yourself. Delegate:
- ask_events for finding events, seats, and eligibility;
- ask_registration for the student's registrations and any registration, waitlist, or confirmation-message action.
Give specialists complete requests and include event ids once known. Only perform side effects when the student clearly asked to register or join a waitlist.
Answer briefly using only specialist results."""

EVENTS_SYSTEM="""You are the event discovery specialist. You can only read event listings and check eligibility.
Find the relevant event, report event_id, title, schedule, venue, seats and eligibility. Never register or
waitlist a student. Be concise."""
REGISTRATION_SYSTEM="""You are the registration desk specialist, acting for student {student_id} only.
Before registering, call check_registration_limit. Registration also enforces eligibility from database rules.
Never invent or override policy. Only register when the student's request clearly asks for it. If an event is full,
offer or perform join_waitlist only when the student asked or accepted the waitlist. Confirm completed actions with notify_student."""

def run_tool(toolset,db,key,name,args):
    try:
        if name in toolset.DELEGATES:return toolset.delegate(name,args,key),False
        if name in toolset.SIDE_EFFECTS:
            result,fresh=db.once(key,name,lambda:toolset.call(name,args)); return result,not fresh
        return toolset.call(name,args),False
    except AgentError: raise
    except NotImplementedError:return {"error":"not_implemented","hint":f"{name} is not available yet."},False
    except Exception as e:return {"error":"tool_failed","hint":f"{name} failed ({type(e).__name__}). Try another way or tell the user."},False

def run_specialist(agent,system,toolset,*,db,provider,task,parent_key,on_step=None):
    contents=[{"role":"user","text":task}]; functions=list(toolset.functions().values()); used=[]; seq=0
    while seq<SPECIALIST_MAX_STEPS:
        turn=provider.generate(system,contents,functions); seq+=1
        if not turn.tool_calls:return {"agent":agent,"answer":turn.text or "","tools_used":used}
        calls=[{"name":c.name,"args":c.args} for c in turn.tool_calls]
        contents.append({"role":"model","text":turn.text,"raw":turn.raw,"tool_calls":calls})
        for call in turn.tool_calls:
            seq+=1; key=idempotency_key(parent_key,seq,call.name,call.args)
            started=time.perf_counter(); result,replayed=run_tool(toolset,db,key,call.name,call.args)
            used.append(call.name)
            if on_step:on_step({"agent":agent,"kind":"tool","tool":call.name,"args":call.args,"result":result,
                                  "ok":"error" not in result,"replayed":replayed,"ms":round((time.perf_counter()-started)*1000)})
            contents.append({"role":"tool","name":call.name,"result":result})
    return {"agent":agent,"error":"specialist_step_limit","tools_used":used,"hint":"Ask the student to simplify the request."}

class SupervisorTools(Toolset):
    TOOL_NAMES=("ask_events","ask_registration"); DELEGATES=TOOL_NAMES
    def __init__(self,db,providers,student_id,on_step=None):self.db,self.providers,self.student_id,self.on_step=db,providers,student_id,on_step
    def ask_events(self,question:str)->dict:
        """Ask the read-only event specialist to find events or check eligibility.
        Use for discovery, availability and qualification questions. It cannot change data.
        Args: question: complete event-search request.
        Returns: specialist answer and tools used."""
        raise RuntimeError("delegations run through delegate()")
    def ask_registration(self,request:str)->dict:
        """Ask the registration specialist about this student's registrations or to register, waitlist, or notify.
        Use for requested actions and account questions. It can change data, but only for the bound student.
        Args: request: complete registration request.
        Returns: specialist answer and tools used."""
        raise RuntimeError("delegations run through delegate()")
    def delegate(self,name,args,key):
        field="question" if name=="ask_events" else "request"
        if set(args)!={field} or not isinstance(args[field],str) or not args[field].strip():
            return {"error":"invalid_arguments","hint":f"{name} takes one non-empty string: {field}."}
        if self.on_step:self.on_step({"agent":"supervisor","kind":"delegate","tool":name,"args":args})
        if name=="ask_events":
            return run_specialist("events",EVENTS_SYSTEM,EventCatalogueTools(self.db,self.student_id),
                db=self.db,provider=self.providers["events"],task=args[field],parent_key=key,on_step=self.on_step)
        return run_specialist("registration",REGISTRATION_SYSTEM.format(student_id=self.student_id),
            RegistrationTools(self.db,self.student_id),db=self.db,provider=self.providers["registration"],
            task=args[field],parent_key=key,on_step=self.on_step)
