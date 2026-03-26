"""
ai_agents/api.py
────────────────
FastAPI application to expose the AI Agents functionality.
Provides 0ms-latency retrieval of the latest decisions via Redis cache,
and a trigger endpoint to force a pipeline run.
"""

import logging
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse

from ai_agents.db import storage
from ai_agents.tasks import run_pipeline
from ai_agents.config.celery_config import REDIS_URL
import redis

logger = logging.getLogger(__name__)

app = FastAPI(
    title="AI Portfolio Intelligence API",
    description="Live market signals, probabilistic predictions, and adaptive asset allocation.",
    version="1.0.0"
)

# Optional Redis connection purely for health checks
try:
    _redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception:
    _redis = None

@app.get("/health")
async def health_check():
    """
    Check if the API and its underlying datastores are healthy.
    """
    try:
        cache_status = "ok" if _redis and _redis.ping() else "down"
    except Exception:
        cache_status = "down"
    return {"status": "ok", "redis_cache": cache_status, "agent_version": "1.0"}

@app.get("/live-advice")
async def get_live_advice():
    """
    Retrieves the latest AI-generated market intelligence and portfolio advice.
    Reads directly from Redis cache for 0ms latency. Falls back to NDJSON.
    Does NOT block for live data fetching.
    """
    latest = storage.get_latest()
    if not latest:
        # If cache is entirely empty (first run), trigger a background job
        run_pipeline.delay()
        return JSONResponse(
            status_code=202,
            content={
                "message": "AI Agents pipeline is initialising. Data will be available shortly.",
                "status": "pending"
            }
        )
        
    return latest

@app.post("/run-pipeline")
async def trigger_pipeline():
    """
    Asynchronously force the Celery pipeline to run immediately.
    """
    task = run_pipeline.delay()
    return {"message": "Pipeline triggered", "task_id": task.id}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("ai_agents.api:app", host="0.0.0.0", port=8000, reload=True)
