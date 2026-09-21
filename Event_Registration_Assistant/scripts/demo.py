"""End-to-end event registration demo. No API key is needed."""
import argparse,os,tempfile
from scripts._term import CYAN,DIM,GREEN,RED,RESET,print_step
QUESTIONS=[("22CS045","Is the AI & Data Science Meetup available? If it is, register me and send a confirmation."),
           ("22EC031","Can I register for the Cloud Computing Workshop?")]
class Crash(BaseException): pass
def counts(db):
    return f"registrations {db.count('registration')}   notifications {db.count('notification')}   idempotency keys {db.count('idempotency')}"
def main():
    p=argparse.ArgumentParser();p.add_argument("--real",action="store_true");p.add_argument("--crash",action="store_true");a=p.parse_args()
    tmp=tempfile.mkdtemp(prefix="event-demo-")
    os.environ["AGENT_DB"]=os.path.join(tmp,"agent.db");os.environ["EVENT_DB"]=os.path.join(tmp,"event.db")
    from app.config import make_providers,open_stores
    from app.worker import Worker
    store,db=open_stores();providers=make_providers(mock=not a.real)
    print(f"{DIM}databases in {tmp}   model: {providers['supervisor'].model}{RESET}")
    print(f"{DIM}before: {counts(db)}{RESET}\n")
    questions=QUESTIONS[:1] if a.crash else QUESTIONS
    for participant_id,text in questions:
        thread=store.create_thread(participant_id);run_id=store.enqueue(thread,text,providers["supervisor"].model)
        print(f"{CYAN}{participant_id}>{RESET} {text}")
        if a.crash:
            real_once=db.once
            def once_then_die(key,tool_name,effect):
                result=real_once(key,tool_name,effect)
                if tool_name=="register_event": raise Crash()
                return result
            db.once=once_then_die
            try: Worker(store,db,providers,worker_id="worker-A",lease_seconds=60,on_step=print_step).run_once()
            except Crash:
                db.once=real_once
                print(f"\n  {RED}worker-A died right after registration{RESET}")
                print(f"  {DIM}{counts(db)}; run is '{store.get_run(run_id)['status']}'{RESET}")
                store.clock=lambda:__import__('time').time()+61
                print(f"  {DIM}...lease expires, worker-B claims the run{RESET}\n")
            Worker(store,db,providers,worker_id="worker-B",lease_seconds=60,on_step=print_step).run_until_idle()
        else: Worker(store,db,providers,worker_id="demo-worker",on_step=print_step).run_until_idle()
        run=store.get_run(run_id); colour=GREEN if run["status"]=="succeeded" else RED
        reply=store.load_history(thread)[-1]["text"] if run["status"]=="succeeded" else run["error_code"]
        print(f"{colour}assistant>{RESET} {reply}")
        print(f"{DIM}run {run_id[:8]} {run['status']} after {run['attempts']} attempt(s), {run['tokens_in']}+{run['tokens_out']} supervisor tokens{RESET}\n")
    print(f"after: {counts(db)}")
    if a.crash:
        ok=db.count("registration")==2 and db.count("notification")==1
        print(f"{GREEN}PASS: one new registration, one confirmation{RESET}" if ok else f"{RED}FAIL: duplicates{RESET}")
if __name__=="__main__": main()
