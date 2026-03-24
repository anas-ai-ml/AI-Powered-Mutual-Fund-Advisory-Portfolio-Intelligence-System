"""
ai_agents/config/celery_config.py
─────────────────────────────────
Configuration for the Celery app and Redbeat/Beat scheduler.
Assumes Redis is running locally on port 6379.
"""

from celery.schedules import crontab
import os

# Default to localhost if not specified in env
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# Broker and Result Backend
broker_url = f"{REDIS_URL}/0"
result_backend = f"{REDIS_URL}/1"

# Serialization
task_serializer = "json"
result_serializer = "json"
accept_content = ["json"]
timezone = "Asia/Kolkata"

# Beat schedule: 
beat_schedule = {
    "run-ai-pipeline-every-15-min": {
        "task": "ai_agents.tasks.run_pipeline",
        "schedule": crontab(minute="*/15"),
        "args": (),
    },
    "update-fund-universe-daily": {
        "task": "ai_agents.tasks.update_fund_universe",
        "schedule": crontab(hour="1", minute="0"), # Run daily at 1 AM
        "args": (),
    },
}

# Task execution limits
task_soft_time_limit = 120  # 2 minutes
task_time_limit = 150       # 2.5 minutes
worker_prefetch_multiplier = 1
