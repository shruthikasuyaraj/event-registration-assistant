"""Queue one real user question: python -m scripts.ask --student 22CS045 "List AI events" """
import argparse
from app.config import open_stores,make_providers
from app.worker import Worker
def main():
    p=argparse.ArgumentParser(); p.add_argument("--student",required=True); p.add_argument("text"); a=p.parse_args()
    store,_=open_stores(); providers=make_providers(mock=False)
    thread=store.create_thread(a.student); run=store.enqueue(thread,a.text,providers["supervisor"].model)
    print(run)
    Worker(store,_,providers).run_until_idle()
if __name__=="__main__":main()
