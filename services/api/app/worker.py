"""Run the worker: python -m app.worker  (needs WORKER_DATABASE_URL and DATABASE_URL)."""
from app.queue import run_forever

if __name__ == "__main__":
    run_forever()
