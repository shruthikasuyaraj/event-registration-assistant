"""event.db: participants, events, registrations, waitlist entries and notifications."""
import json
import time
from collections.abc import Callable
from pathlib import Path
from app.db import connect, transaction

SCHEMA = Path(__file__).resolve().parent.parent / "schema" / "event.sql"

class EventDb:
    def __init__(self, path: str = ":memory:", clock: Callable[[], float] = time.time):
        self.conn = connect(path)
        self.clock = clock

    def transaction(self):
        return transaction(self.conn)

    def migrate(self) -> None:
        self.conn.executescript(SCHEMA.read_text())
        if self.conn.execute("SELECT count(*) FROM participant").fetchone()[0]:
            return
        with self.transaction() as c:
            c.executemany("INSERT INTO participant VALUES (?, ?, ?, ?, ?)", [
                (1, "22CS045", "Priya Raman", "CSE", "student"),
                (2, "22IT017", "Arjun Kumar", "IT", "student"),
                (3, "22EC031", "Divya Sekar", "ECE", "student")])
            c.executemany("INSERT INTO event VALUES (?, ?, ?, ?, ?, ?, ?, 0)", [
                (1, "AI & Data Science Meetup", "2026-10-10", "Main Auditorium", 2, 2, "all"),
                (2, "Cloud Computing Workshop", "2026-10-12", "Lab 3", 1, 1, "IT"),
                (3, "Women in Tech Panel", "2026-10-15", "Seminar Hall", 3, 3, "all"),
                (4, "Advanced Robotics Lab", "2026-10-18", "Robotics Lab", 1, 0, "ECE")])
            c.executemany("INSERT INTO policy VALUES (?, ?)", [
                ("max_event_registrations", 2),
                ("max_waitlist_entries", 3)])
            c.execute("INSERT INTO registration (participant_id, event_id, status, created_at) VALUES (1, 3, 'registered', ?)", (self.clock(),))
            c.execute("UPDATE event SET seats_available = seats_available - 1 WHERE id = 3")

    def get_participant(self, participant_id: str) -> dict | None:
        r=self.conn.execute("SELECT * FROM participant WHERE participant_id=?",(participant_id,)).fetchone()
        return dict(r) if r else None

    def get_event(self,event_id:int)->dict|None:
        r=self.conn.execute("SELECT * FROM event WHERE id=?",(event_id,)).fetchone()
        return dict(r) if r else None

    def policy(self,name:str)->int:
        return self.conn.execute("SELECT value FROM policy WHERE name=?",(name,)).fetchone()[0]

    def active_registrations(self,participant_pk:int)->list[dict]:
        rows=self.conn.execute(
            "SELECT r.event_id,e.name,r.status FROM registration r JOIN event e ON e.id=r.event_id "
            "WHERE r.participant_id=? AND r.status IN ('registered','waitlisted') ORDER BY r.id",(participant_pk,)).fetchall()
        return [dict(r) for r in rows]

    def search_events(self,text:str,limit:int=5)->list[dict]:
        like=f"%{text.strip()}%"
        rows=self.conn.execute(
            "SELECT id,name,event_date,venue,seat_limit,seats_available,eligibility_group FROM event "
            "WHERE name LIKE ? OR venue LIKE ? OR event_date LIKE ? ORDER BY event_date LIMIT ?",
            (like,like,like,limit)).fetchall()
        return [dict(r) for r in rows]

    def count(self,table:str)->int:
        assert table.isidentifier()
        return self.conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0]

    def register(self,participant_pk:int,event_id:int)->str:
        """Returns registered, already_registered, or no_seats. Safe to repeat."""
        with self.transaction() as c:
            existing=c.execute("SELECT status FROM registration WHERE participant_id=? AND event_id=?",
                               (participant_pk,event_id)).fetchone()
            if existing and existing["status"]=="registered":
                return "already_registered"
            event=c.execute("SELECT seats_available,version FROM event WHERE id=?",(event_id,)).fetchone()
            if event is None: return "unknown_event"
            took=c.execute("UPDATE event SET seats_available=seats_available-1,version=version+1 "
                           "WHERE id=? AND seats_available>0 AND version=?",(event_id,event["version"])).rowcount
            if not took: return "no_seats"
            if existing and existing["status"]=="waitlisted":
                c.execute("UPDATE registration SET status='registered',created_at=? WHERE participant_id=? AND event_id=?",
                          (self.clock(),participant_pk,event_id))
            else:
                c.execute("INSERT INTO registration(participant_id,event_id,status,created_at) VALUES (?,?, 'registered',?)",
                          (participant_pk,event_id,self.clock()))
            return "registered"

    def waitlist(self,participant_pk:int,event_id:int)->str:
        with self.transaction() as c:
            existing=c.execute("SELECT status FROM registration WHERE participant_id=? AND event_id=?",
                               (participant_pk,event_id)).fetchone()
            if existing:
                return "already_registered" if existing["status"]=="registered" else "already_waitlisted"
            event=c.execute("SELECT id FROM event WHERE id=?",(event_id,)).fetchone()
            if event is None:return "unknown_event"
            c.execute("INSERT INTO registration(participant_id,event_id,status,created_at) VALUES (?,?, 'waitlisted',?)",
                      (participant_pk,event_id,self.clock()))
            return "waitlisted"

    def record_notification(self,participant_id:str,message:str,dedupe_key:str)->tuple[int,bool]:
        cur=self.conn.execute(
            "INSERT INTO notification(participant_id,message,dedupe_key,created_at) VALUES (?,?,?,?) "
            "ON CONFLICT(dedupe_key) DO NOTHING",(participant_id,message,dedupe_key,self.clock()))
        if cur.rowcount==1:return cur.lastrowid,True
        return self.conn.execute("SELECT id FROM notification WHERE dedupe_key=?",(dedupe_key,)).fetchone()[0],False

    def once(self,key:str,tool_name:str,effect:Callable[[],dict])->tuple[dict,bool]:
        with self.transaction() as c:
            row=c.execute("SELECT result FROM idempotency WHERE key=?",(key,)).fetchone()
            if row is not None:return json.loads(row["result"]),False
            result=effect()
            c.execute("INSERT INTO idempotency(key,tool_name,result,created_at) VALUES (?,?,?,?)",
                      (key,tool_name,json.dumps(result,default=str),self.clock()))
            return result,True
