"""event.db: students, events, eligibility and registrations. SQL stays here."""
import json, time
from collections.abc import Callable
from pathlib import Path
from app.db import connect, transaction

SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "event.sql"

class EventDb:
    def __init__(self, path=":memory:", clock: Callable[[], float]=time.time):
        self.conn=connect(path); self.clock=clock
    def transaction(self): return transaction(self.conn)
    def migrate(self):
        self.conn.executescript(SCHEMA.read_text())
        if self.conn.execute("SELECT count(*) FROM student").fetchone()[0]: return
        with self.transaction() as c:
            c.executemany("INSERT INTO student VALUES (?,?,?,?,?)", [
                (1,"22CS045","Priya Raman","CSE",2),
                (2,"22IT017","Arjun Kumar","IT",2),
                (3,"22EC031","Divya Sekar","ECE",3),
                (4,"22CS099","Kavin Raj","CSE",3)])
            c.executemany("INSERT INTO event VALUES (?,?,?,?,?,?,?,0)", [
                (1,"AI & Backend Engineering Workshop","Hands-on APIs, agents and backend design.","Lab Block A","2026-09-28 10:00",2,2),
                (2,"Cloud Career Talk","Industry talk on cloud and DevOps careers.","Auditorium","2026-09-29 14:00",1,1),
                (3,"Competitive Programming Sprint","Timed contest with DSA problems.","Lab Block B","2026-10-02 09:00",3,3),
                (4,"ECE Embedded Systems Meetup","Embedded systems projects and careers.","ECE Seminar Hall","2026-10-03 11:00",2,2)])
            c.executemany("INSERT INTO eligibility_rule VALUES (?,?,?,?,?)", [
                (1,1,"CSE",2,4),(2,1,"IT",2,4),
                (3,2,None,2,4),
                (4,3,None,2,4),
                (5,4,"ECE",2,4)])
            c.executemany("INSERT INTO policy VALUES (?,?)", [("max_active_registrations",2)])
            # Seed one registration so a student can be tested against the policy.
            c.execute("INSERT INTO registration(student_id,event_id,created_at) VALUES (?,?,?)",(4,3,self.clock()))
            c.execute("UPDATE event SET seats_available=seats_available-1 WHERE id=3")
            c.execute("INSERT INTO registration(student_id,event_id,created_at) VALUES (?,?,?)",(4,2,self.clock()))
            c.execute("UPDATE event SET seats_available=0 WHERE id=2")

    def count(self, table): 
        assert table.isidentifier()
        return self.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
    def get_student(self, student_ref):
        r=self.conn.execute("SELECT * FROM student WHERE student_id=?",(student_ref,)).fetchone()
        return dict(r) if r else None
    def get_event(self,event_id):
        r=self.conn.execute("SELECT * FROM event WHERE id=?",(event_id,)).fetchone()
        return dict(r) if r else None
    def list_events(self,text="",limit=10):
        like=f"%{text.strip()}%"
        rows=self.conn.execute("""SELECT * FROM event WHERE ?='' OR title LIKE ? OR description LIKE ?
            OR venue LIKE ? ORDER BY starts_at LIMIT ?""",(text.strip(),like,like,like,limit)).fetchall()
        return [dict(r) for r in rows]
    def rules(self,event_id):
        return [dict(r) for r in self.conn.execute("SELECT * FROM eligibility_rule WHERE event_id=?",(event_id,))]
    def registrations(self,student_pk):
        rows=self.conn.execute("""SELECT e.id event_id,e.title,e.starts_at FROM registration r JOIN event e ON e.id=r.event_id
            WHERE r.student_id=? ORDER BY e.starts_at""",(student_pk,)).fetchall()
        return [dict(r) for r in rows]
    def is_eligible(self,student,event_id):
        rules=self.rules(event_id)
        if not rules: return True, []
        for r in rules:
            dept_ok = r["dept"] is None or r["dept"] == student["dept"]
            year_ok = (r["min_year"] is None or student["year"] >= r["min_year"]) and (r["max_year"] is None or student["year"] <= r["max_year"])
            if dept_ok and year_ok: return True, []
        reasons=[]
        if any(r["dept"] for r in rules): reasons.append("student department does not match the event eligibility")
        if any((r["min_year"] or r["max_year"]) for r in rules): reasons.append("student year does not match the event eligibility")
        return False,reasons
    def register(self,student_pk,event_id):
        with self.transaction() as c:
            if c.execute("SELECT 1 FROM registration WHERE student_id=? AND event_id=?",(student_pk,event_id)).fetchone():
                return "already_registered"
            if c.execute("SELECT 1 FROM waitlist WHERE student_id=? AND event_id=?",(student_pk,event_id)).fetchone():
                return "waitlisted"
            ev=c.execute("SELECT version,seats_available FROM event WHERE id=?",(event_id,)).fetchone()
            if ev is None: return "unknown_event"
            took=c.execute("""UPDATE event SET seats_available=seats_available-1,version=version+1
                WHERE id=? AND seats_available>0 AND version=?""",(event_id,ev["version"])).rowcount
            if not took: return "full"
            c.execute("INSERT INTO registration(student_id,event_id,created_at) VALUES(?,?,?)",(student_pk,event_id,self.clock()))
            return "registered"
    def join_waitlist(self,student_pk,event_id):
        with self.transaction() as c:
            if c.execute("SELECT 1 FROM registration WHERE student_id=? AND event_id=?",(student_pk,event_id)).fetchone():
                return "already_registered"
            if c.execute("SELECT 1 FROM waitlist WHERE student_id=? AND event_id=?",(student_pk,event_id)).fetchone():
                return "already_waitlisted"
            ev=c.execute("SELECT id,seats_available FROM event WHERE id=?",(event_id,)).fetchone()
            if ev is None: return "unknown_event"
            if ev["seats_available"]>0: return "seats_available"
            c.execute("INSERT INTO waitlist(student_id,event_id,created_at) VALUES(?,?,?)",(student_pk,event_id,self.clock()))
            return "waitlisted"
    def record_notification(self,student_ref,message,dedupe_key):
        cur=self.conn.execute("""INSERT INTO notification(student_ref,message,dedupe_key,created_at)
            VALUES(?,?,?,?) ON CONFLICT(dedupe_key) DO NOTHING""",(student_ref,message,dedupe_key,self.clock()))
        if cur.rowcount==1: return cur.lastrowid,True
        return self.conn.execute("SELECT id FROM notification WHERE dedupe_key=?",(dedupe_key,)).fetchone()[0],False
    def once(self,key,tool_name,effect):
        with self.transaction() as c:
            row=c.execute("SELECT result FROM idempotency WHERE key=?",(key,)).fetchone()
            if row: return json.loads(row["result"]),False
            result=effect()
            c.execute("INSERT INTO idempotency VALUES(?,?,?,?)",(key,tool_name,json.dumps(result),self.clock()))
            return result,True
