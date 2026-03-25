"""
ai_layer/scheduler/updater.py
──────────────────────────────
Background scheduler that keeps AI layer data fresh.

Uses APScheduler BackgroundScheduler to:
  1. Fetch market snapshot + macro indicators every 15 minutes.
  2. Recompute signals.
  3. Store results in a thread-safe module-level cache dict.

The dashboard calls ``get_cached_intelligence()`` which returns
immediately from the cache — it never blocks on a network call.

Usage:
    from ai_layer.scheduler.updater import start_scheduler, get_cached_intelligence
    start_scheduler()   # Call once at app startup
    intel = get_cached_intelligence()
"""

import logging
import threading
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# ── Thread-safe cache ─────────────────────────────────────────────────────────
_LOCK = threading.Lock()
_CACHE: Dict[str, Any] = {}
_SCHEDULER_STARTED = False

# ── Refresh interval ──────────────────────────────────────────────────────────
_REFRESH_INTERVAL_MINUTES = 20
_MACRO_REFRESH_INTERVAL_HOURS = 6


def _do_refresh() -> None:
    """
    Fetch fresh data from all sources and update the cache.
    Called by the scheduler on a background thread; errors are caught so
    a transient network failure never kills the scheduler job.
    """
    try:
        from ai_layer.data_ingestion.market_data import get_market_snapshot
        from ai_layer.data_ingestion.macro_data import get_macro_indicators
        from ai_layer.signal_engine.market_signals import generate_signals

        logger.info("ai_layer scheduler: starting data refresh...")

        market_snapshot = get_market_snapshot(use_cache=False)
        macro_indicators = get_macro_indicators(use_cache=False)
        signals = generate_signals(market_snapshot, macro_indicators)

        with _LOCK:
            _CACHE["market_snapshot"] = market_snapshot
            _CACHE["macro_indicators"] = macro_indicators
            _CACHE["signals"] = signals
            _CACHE["last_updated"] = datetime.now().isoformat(timespec="seconds")

        try:
            from data.cache.cache_manager import save_signals, save_macro_data

            save_signals(signals)
            save_macro_data(macro_indicators)
        except Exception as e:
            logger.warning(f"Failed to save to file cache: {e}")

        logger.info(
            "ai_layer scheduler: cache refreshed at %s. "
            "Live market: %s/%s tickers. Macro source: %s.",
            _CACHE["last_updated"],
            market_snapshot.get("_meta", {}).get("live_count", 0),
            market_snapshot.get("_meta", {}).get("total_count", 6),
            macro_indicators.get("source", "unknown"),
        )

    except Exception as exc:
        logger.error("ai_layer scheduler: refresh failed — %s", exc)
        try:
            from data.cache.cache_manager import (
                load_signals_fallback,
                load_macro_fallback,
            )

            cached_signals = load_signals_fallback()
            cached_macro = load_macro_fallback()
            with _LOCK:
                _CACHE["signals"] = cached_signals
                _CACHE["macro_indicators"] = cached_macro
                _CACHE["last_updated"] = datetime.now().isoformat(timespec="seconds")
            logger.info(
                "ai_layer scheduler: restored from file cache after refresh failure"
            )
        except Exception as e:
            logger.error("ai_layer scheduler: even cache fallback failed — %s", e)


def start_scheduler() -> None:
    """
    Start the APScheduler background job if not already running.
    Also performs an immediate first refresh so the cache is populated
    before the first user sees the dashboard.

    Safe to call multiple times — only one scheduler will be started.
    """
    global _SCHEDULER_STARTED
    if _SCHEDULER_STARTED:
        return

    # Immediate first refresh (synchronous, blocks for a few seconds)
    logger.info("ai_layer scheduler: performing initial data fetch...")
    _do_refresh()

    try:
        from apscheduler.schedulers.background import BackgroundScheduler

        scheduler = BackgroundScheduler(
            job_defaults={"misfire_grace_time": 60},
            timezone="Asia/Kolkata",
        )
        scheduler.add_job(
            _do_refresh,
            trigger="interval",
            minutes=_REFRESH_INTERVAL_MINUTES,
            id="ai_layer_refresh",
            replace_existing=True,
        )
        scheduler.start()
        _SCHEDULER_STARTED = True
        logger.info(
            "ai_layer scheduler: started — refresh every %d min.",
            _REFRESH_INTERVAL_MINUTES,
        )

    except ImportError:
        logger.warning(
            "APScheduler not installed. ai_layer cache will only refresh on start-up. "
            "Run: pip install APScheduler>=3.10"
        )
        _SCHEDULER_STARTED = True  # Prevent repeated attempts


def get_cached_intelligence() -> Dict[str, Any]:
    """
    Return the most recently cached intelligence data.

    If the cache is empty (scheduler not yet started), performs a
    synchronous fetch as fallback. If that fails, uses file cache.

    Returns
    -------
    dict
        ``market_snapshot``  – from market_data.py
        ``macro_indicators`` – from macro_data.py
        ``signals``          – from market_signals.py
        ``last_updated``     – ISO timestamp of last refresh
    """
    with _LOCK:
        if _CACHE:
            return dict(_CACHE)

    logger.info("ai_layer: cache empty, running synchronous fetch...")
    try:
        _do_refresh()
    except Exception as e:
        logger.warning(f"Synchronous fetch failed: {e}")
        try:
            from data.cache.cache_manager import (
                load_signals_fallback,
                load_macro_fallback,
            )

            with _LOCK:
                _CACHE["signals"] = load_signals_fallback()
                _CACHE["macro_indicators"] = load_macro_fallback()
                _CACHE["last_updated"] = datetime.now().isoformat(timespec="seconds")
            logger.info("ai_layer: restored from file cache")
        except Exception as ce:
            logger.error(f"File cache fallback failed: {ce}")

    with _LOCK:
        return dict(_CACHE)
