"""Worker process for queued event-registration runs."""
from app.config import open_stores,make_providers
from app.worker import Worker
def main():
    store,db=open_stores()
    Worker(store,db,make_providers(mock=False)).run_forever()
if __name__=="__main__":main()
