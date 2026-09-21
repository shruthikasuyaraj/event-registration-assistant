"""Event tools split between a read-only events specialist and a registration specialist."""
from datetime import datetime, timezone
from app.event_db import EventDb
from app.idempotency import notification_dedupe_key
from app.tools.dispatch import dispatch

class Toolset:
    SIDE_EFFECTS=(); DELEGATES=(); TOOL_NAMES=()
    def functions(self): return {n:getattr(self,n) for n in self.TOOL_NAMES}
    def call(self,name,args): return dispatch(self.functions(),name,args)

class EventCatalogueTools(Toolset):
    """Read-only event discovery and eligibility checks."""
    TOOL_NAMES=("list_events","check_eligibility")
    def __init__(self,db,student_id): self.db,self.student_id=db,student_id
    def list_events(self,text:str="")->dict:
        """List upcoming campus events matching optional words in title, description or venue.
        Use for event discovery and availability questions. Do not use it to register or waitlist.
        Read-only: it changes no data.
        Args: text: Optional search words such as "AI", "cloud", or "programming".
        Returns: {"events":[{"event_id","title","venue","starts_at","seats_available","seats_total"}]}.
        """
        return {"events":[{"event_id":e["id"],"title":e["title"],"venue":e["venue"],"starts_at":e["starts_at"],
                           "seats_available":e["seats_available"],"seats_total":e["seats_total"]}
                        for e in self.db.list_events(text)]}
    def check_eligibility(self,event_id:int)->dict:
        """Check whether the current student is eligible for one event using database eligibility rules.
        Use before registration or waitlisting and when the student asks whether they qualify.
        Read-only: it changes no data. The tool, not the model, decides eligibility.
        Args: event_id: Integer id returned by list_events.
        Returns: {"eligible": bool, "reasons":[str], "event": {...}} or unknown_event/unknown_student.
        """
        s=self.db.get_student(self.student_id); e=self.db.get_event(event_id)
        if not s: return {"error":"unknown_student","hint":"The current student is not in the event system."}
        if not e: return {"error":"unknown_event","hint":"Use list_events to find a valid event_id."}
        ok,reasons=self.db.is_eligible(s,event_id)
        return {"eligible":ok,"reasons":reasons,"event":{"event_id":e["id"],"title":e["title"],
                "seats_available":e["seats_available"],"venue":e["venue"],"starts_at":e["starts_at"]}}

class RegistrationTools(Toolset):
    """Write-capable registration desk bound to exactly one student."""
    TOOL_NAMES=("get_student","check_registration_limit","register","join_waitlist","notify_student")
    SIDE_EFFECTS=("register","join_waitlist","notify_student")
    def __init__(self,db,student_id,clock=lambda:datetime.now(timezone.utc)):
        self.db,self.student_id,self.clock=db,student_id,clock
    def _student(self):
        s=self.db.get_student(self.student_id)
        if not s: raise LookupError(f"student {self.student_id} not found")
        return s
    def get_student(self)->dict:
        """Get the current student's profile and current registrations.
        Use for "what am I registered for" or before explaining the account.
        Read-only: it changes no data and cannot act for another student.
        Returns: student details plus registrations with event_id, title and start time.
        """
        s=self._student()
        return {"student_id":s["student_id"],"name":s["name"],"dept":s["dept"],"year":s["year"],
                "registrations":self.db.registrations(s["id"])}
    def check_registration_limit(self)->dict:
        """Check the database policy for the maximum number of active registrations.
        Use before register or when the student asks whether another registration is allowed.
        Read-only: it changes no data. The policy value comes from the policy table, not the prompt.
        Returns: {"can_register": bool, "current": int, "limit": int, "reasons":[str]}.
        """
        s=self._student(); current=len(self.db.registrations(s["id"]))
        limit=self.db.conn.execute("SELECT value FROM policy WHERE name='max_active_registrations'").fetchone()[0]
        reasons=[] if current<limit else [f"already has {current} of {limit} allowed active registrations"]
        return {"can_register":not reasons,"current":current,"limit":limit,"reasons":reasons}
    def register(self,event_id:int)->dict:
        """Register the current student for one event. CHANGES DATA: consumes one seat.
        Use only after the student clearly asks to register and eligibility plus the registration-limit check allow it.
        Repeat calls for the same student/event are safe and return already_registered. Never use to merely check availability.
        Args: event_id: Integer id returned by list_events.
        Returns: registered/already_registered, or full, not_allowed, ineligible, unknown_event.
        """
        limit=self.check_registration_limit()
        if not limit["can_register"]: return {"error":"not_allowed","reasons":limit["reasons"],"hint":"Do not retry."}
        s=self._student(); e=self.db.get_event(event_id)
        if not e:return {"error":"unknown_event","hint":"Use list_events first."}
        ok,reasons=self.db.is_eligible(s,event_id)
        if not ok:return {"error":"ineligible","reasons":reasons,"hint":"Do not retry."}
        status=self.db.register(s["id"],event_id)
        if status=="unknown_event": return {"error":"unknown_event"}
        if status=="full": return {"error":"full","hint":"The event is full; offer the waitlist."}
        return {"event_id":event_id,"title":e["title"],"status":status}
    def join_waitlist(self,event_id:int)->dict:
        """Join the waitlist for a full event. CHANGES DATA: creates a waitlist entry.
        Use only when the student explicitly asks to join the waitlist or accepts that the event is full.
        Check eligibility first. Repeat calls are safe. Do not use while seats are available.
        Args: event_id: Integer id returned by list_events.
        Returns: waitlisted/already_waitlisted, or ineligible, seats_available, unknown_event.
        """
        s=self._student(); e=self.db.get_event(event_id)
        if not e:return {"error":"unknown_event"}
        ok,reasons=self.db.is_eligible(s,event_id)
        if not ok:return {"error":"ineligible","reasons":reasons,"hint":"Do not retry."}
        status=self.db.join_waitlist(s["id"],event_id)
        if status=="seats_available": return {"error":"seats_available","hint":"Register instead."}
        return {"event_id":event_id,"title":e["title"],"status":status}
    def notify_student(self,message:str)->dict:
        """Send the current student a short confirmation message. CHANGES DATA: records a notification.
        Use only to confirm a completed registration or waitlist action, never to answer a question.
        The same message on the same day is sent once, so repeats are safe.
        Args: message: 1 to 160 characters.
        Returns: {"notification_id","status":"queued","duplicate":bool}, or invalid_message.
        """
        if not message.strip() or len(message)>160:return {"error":"invalid_message","hint":"message must be 1 to 160 characters."}
        key=notification_dedupe_key(self.student_id,message,self.clock().date())
        nid,created=self.db.record_notification(self.student_id,message,key)
        return {"notification_id":nid,"status":"queued","duplicate":not created}
