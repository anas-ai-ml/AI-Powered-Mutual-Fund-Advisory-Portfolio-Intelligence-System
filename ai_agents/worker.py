"""
ai_agents/worker.py
───────────────────
Entry point for the Celery worker and Celery Beat scheduler.
Run this using: celery -A ai_agents.worker worker -B --loglevel=info
"""

# Import the Celery app instance from tasks.py
from ai_agents.tasks import app

if __name__ == "__main__":
    app.start()
