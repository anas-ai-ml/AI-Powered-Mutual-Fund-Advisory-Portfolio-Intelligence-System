"""
ai_agents/db/storage.py
───────────────────────
Persists system outputs for tracking.
1. JSON lines on-disk storage
2. Redis cache for instantaneous API retrieval
"""

import json
import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
import redis

from ai_agents.config.celery_config import REDIS_URL

logger = logging.getLogger(__name__)

# Constants
DATA_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "data"))
HISTORY_FILE = os.path.join(DATA_DIR, "history.ndjson")
LATEST_KEY = "ai_agents:latest"

# Redis Client
try:
    _redis = redis.Redis.from_url(REDIS_URL, decode_responses=True)
except Exception as e:
    logger.warning("Could not connect to Redis for storage layer: %s", e)
    _redis = None


def save(
    market: Dict[str, Any],
    signals: Dict[str, Any],
    prediction: Dict[str, Any],
    decision: Dict[str, Any]
) -> None:
    """
    Store pipeline results in both JSON lines file (persistent)
    and Redis cache (fast retrieval).
    """
    record = {
        "timestamp": datetime.now().isoformat(),
        "market": market,
        "signals": signals,
        "prediction": prediction,
        "decision": decision,
    }
    
    # 1. JSON on-disk
    os.makedirs(DATA_DIR, exist_ok=True)
    try:
        with open(HISTORY_FILE, "a") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(f"Failed to write to JSON history: {e}")
        
    # 2. Redis cache
    if _redis:
        try:
            # Expire after 2 hours if scheduler dies
            _redis.set(LATEST_KEY, json.dumps(record), ex=7200)
            logger.info("[Storage] Saved results to Redis.")
        except Exception as e:
            logger.error(f"Failed to write to Redis: {e}")


def get_latest() -> Optional[Dict[str, Any]]:
    """
    Retrieve latest from Redis. If Redis is down, fall back to JSON file.
    """
    # 1. Try Redis
    if _redis:
        try:
            val = _redis.get(LATEST_KEY)
            if val:
                return json.loads(val)
        except Exception as e:
            logger.error(f"Failed to read from Redis (falling back to file): {e}")

    # 2. Try JSON file fallback (read last line efficiently)
    if not os.path.exists(HISTORY_FILE):
        return None
        
    try:
        # Simple read all lines and pick last. 
        # For production with large files, use `tail` or seek.
        with open(HISTORY_FILE, "r") as f:
            lines = f.readlines()
            if lines:
                return json.loads(lines[-1].strip())
    except Exception as e:
        logger.error(f"Failed to read from JSON history: {e}")
        
    return None
