"""Event registration tools split between a read-only event specialist and a registration specialist."""
from datetime import date, datetime, timezone
from app.event_db import EventDb
from app.idempotency import notification_dedupe_key
from app.tools.dispatch import dispatch

class Toolset:
    SIDE_EFFECTS=()
    DELEGATES=()
    TOOL_NAMES=()
    def functions(self): return {n:getattr(self,n) for n in self.TOOL_NAMES}
    def call(self,name,args): return dispatch(self.functions(),name,args)

class EventInfoTools(Toolset):
    """Read-only tools for finding events. This specialist cannot register anyone."""
    TOOL_NAMES=("search_events","get_event")
    def __init__(self,db:EventDb): self.db=db
    def search_events(self,text:str)->dict:
        """Find campus events by name, venue, or date. Use when a participant asks what events exist or whether an event is available. Do not use it to register or waitlist anyone. Changes nothing. Pass a few search words."""
        if not text.strip(): return {"error":"empty_query","hint":"Pass event name, venue, or date words."}
        return {"events":self.db.search_events(text)}
    def get_event(self,event_id:int)->dict:
        """Get one event's current details and remaining seats. Use after search_events when you need exact event data. Do not use it to register or waitlist. Changes nothing."""
        e=self.db.get_event(event_id)
        return {"error":"unknown_event","hint":"Use search_events first."} if e is None else {"event_id":e["id"],"name":e["name"],"event_date":e["event_date"],"venue":e["venue"],"seat_limit":e["seat_limit"],"seats_available":e["seats_available"],"eligibility_group":e["eligibility_group"]}

class RegistrationTools(Toolset):
    TOOL_NAMES=("get_participant","check_eligibility","register_event","join_waitlist","notify_participant")
    SIDE_EFFECTS=("register_event","join_waitlist","notify_participant")
    def __init__(self,db:EventDb,participant_id:str,clock=lambda:datetime.now(timezone.utc)): self.db,self.participant_id,self.clock=db,participant_id,clock
    def _participant(self):
        p=self.db.get_participant(self.participant_id)
        if p is None: raise LookupError(f"participant {self.participant_id} not found")
        return p
    def get_participant(self)->dict:
        """Get the current participant's event-registration record. Use for "what am I registered for" or before changing registrations. Read-only and changes nothing."""
        p=self._participant()
        return {"participant_id":p["participant_id"],"name":p["name"],"dept":p["dept"],"role":p["role"],"registrations":self.db.active_registrations(p["id"])}
    def check_eligibility(self,event_id:int)->dict:
        """Check whether the current participant may register for an event. Use before register_event or join_waitlist. The decision comes from participant data, event eligibility, and policy data; never invent a rule. Read-only."""
        p=self._participant(); e=self.db.get_event(event_id)
        if e is None:return {"eligible":False,"reasons":["unknown event"]}
        reasons=[]
        if e["eligibility_group"]!="all" and e["eligibility_group"]!=p["dept"]:
            reasons.append(f"event is restricted to {e['eligibility_group']} participants")
        active=len(self.db.active_registrations(p["id"]))
        limit=self.db.policy("max_event_registrations")
        if active>=limit: reasons.append(f"already has {active} active registrations/waitlists; limit is {limit}")
        return {"eligible":not reasons,"reasons":reasons}
    def register_event(self,event_id:int)->dict:
        """Register the current participant for an event. CHANGES DATA by consuming one seat. Use only after the participant asked to register and eligibility was allowed. Repeating the same registration is safe."""
        e=self.db.get_event(event_id)
        if e is None:return {"error":"unknown_event"}
        existing=[r for r in self.db.active_registrations(self._participant()["id"]) if r["event_id"]==event_id]
        if existing and existing[0]["status"]=="registered": return {"event_id":event_id,"name":e["name"],"status":"already_registered"}
        verdict=self.check_eligibility(event_id)
        if not verdict["eligible"]: return {"error":"not_allowed","reasons":verdict["reasons"]}
        status=self.db.register(self._participant()["id"],event_id)
        return {"event_id":event_id,"name":e["name"],"status":status} if status!="no_seats" else {"error":"no_seats","hint":"Offer the waitlist."}
    def join_waitlist(self,event_id:int)->dict:
        """Put the current participant on an event waitlist when no seat is available. CHANGES DATA. Use when the participant explicitly asks to waitlist or after a full event is reported."""
        verdict=self.check_eligibility(event_id)
        if not verdict["eligible"]: return {"error":"not_allowed","reasons":verdict["reasons"]}
        e=self.db.get_event(event_id)
        if e is None:return {"error":"unknown_event"}
        if e["seats_available"]>0:return {"error":"seats_available","hint":"Register instead while a seat remains."}
        status=self.db.waitlist(self._participant()["id"],event_id)
        return {"event_id":event_id,"name":e["name"],"status":status}
    def notify_participant(self,message:str)->dict:
        """Send a confirmation message to the current participant. CHANGES DATA by recording a notification. Use after a successful registration or waitlist action; repeating the same text is safe."""
        key=notification_dedupe_key(self.participant_id,message,date.today())
        nid,fresh=self.db.record_notification(self.participant_id,message,key)
        return {"notification_id":nid,"duplicate":not fresh}

