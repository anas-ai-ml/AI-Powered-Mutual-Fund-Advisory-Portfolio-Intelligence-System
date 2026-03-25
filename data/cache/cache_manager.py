"""
data/cache/cache_manager.py
───────────────────────────
Thread-safe file-based cache with JSON persistence.
"""

import json
import os
import threading
import logging
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_CACHE_DIR = Path(__file__).parent
_LOCK = threading.Lock()

_MARKET_CACHE_FILE = _CACHE_DIR / "market_cache.json"
_SIGNALS_CACHE_FILE = _CACHE_DIR / "signals_cache.json"
_MACRO_CACHE_FILE = _CACHE_DIR / "macro_cache.json"

DEFAULT_MARKET_DATA = {
    "stats": {
        "Equity - Large Cap": {"return": 0.13, "volatility": 0.15},
        "Equity - Mid Cap": {"return": 0.15, "volatility": 0.20},
        "Equity - Small Cap": {"return": 0.17, "volatility": 0.25},
        "Equity - Flexi Cap": {"return": 0.14, "volatility": 0.18},
        "Equity - Sectoral": {"return": 0.16, "volatility": 0.22},
        "Equity - Hybrid": {"return": 0.11, "volatility": 0.12},
        "Debt": {"return": 0.075, "volatility": 0.04},
        "Gold": {"return": 0.09, "volatility": 0.15},
    },
    "correlation_matrix": {},
}

DEFAULT_SIGNALS = {
    "market_trend": "neutral",
    "volatility": "medium",
    "global_sentiment": "neutral",
    "inflation_trend": "stable",
    "interest_rate_trend": "stable",
    "usdinr_pressure": "stable",
    "golden_cross": False,
    "vix_level": 15.0,
    "cpi_yoy_pct": 6.0,
    "repo_rate_pct": 6.5,
    "signal_source": "fallback",
}

DEFAULT_MACRO = {
    "cpi_yoy_pct": 6.0,
    "repo_rate_pct": 6.5,
    "bond_yield_pct": 7.1,
    "inflation_trend": "stable",
    "rate_trend": "stable",
    "source": "fallback",
    "fetched_at": None,
}


def _read_json(file_path: Path) -> Optional[Dict]:
    """Read JSON from file. Returns None if file doesn't exist or is invalid."""
    try:
        if file_path.exists():
            with open(file_path, "r") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.warning(f"Cache read failed for {file_path}: {e}")
    return None


def _write_json(file_path: Path, data: Dict) -> bool:
    """Write data to JSON file. Returns True on success."""
    try:
        with open(file_path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        return True
    except IOError as e:
        logger.error(f"Cache write failed for {file_path}: {e}")
        return False


def _get_cache_age(file_path: Path) -> Optional[float]:
    """Return cache age in seconds. None if file doesn't exist."""
    if not file_path.exists():
        return None
    try:
        mtime = os.path.getmtime(file_path)
        return datetime.now().timestamp() - mtime
    except OSError:
        return None


def save_market_data(stats: Dict, correlation_matrix: Any = None) -> None:
    """Save market statistics to cache."""
    with _LOCK:
        data = {
            "stats": stats,
            "correlation_matrix": correlation_matrix.to_dict()
            if correlation_matrix is not None
            else {},
            "cached_at": datetime.now().isoformat(timespec="seconds"),
        }
        _write_json(_MARKET_CACHE_FILE, data)
        logger.info("Market data saved to cache")


def load_market_data(max_age_seconds: float = 3600) -> Optional[Dict]:
    """Load market data from cache if fresh enough. Returns None if expired/missing."""
    with _LOCK:
        age = _get_cache_age(_MARKET_CACHE_FILE)
        if age is not None and age <= max_age_seconds:
            data = _read_json(_MARKET_CACHE_FILE)
            if data:
                logger.info(f"Market data loaded from cache (age: {age:.0f}s)")
                return data

        if age is not None:
            logger.info(f"Market cache expired ({age:.0f}s old)")
        return None


def load_market_data_fallback() -> Dict:
    """Load market data from cache or return defaults."""
    cached = load_market_data(max_age_seconds=float("inf"))
    if cached:
        return cached
    logger.warning("Using DEFAULT market data (no cache)")
    return {"stats": DEFAULT_MARKET_DATA["stats"], "correlation_matrix": {}}


def save_signals(signals: Dict) -> None:
    """Save market signals to cache."""
    with _LOCK:
        data = {
            "signals": signals,
            "cached_at": datetime.now().isoformat(timespec="seconds"),
        }
        _write_json(_SIGNALS_CACHE_FILE, data)
        logger.info("Signals saved to cache")


def load_signals(max_age_seconds: float = 7200) -> Optional[Dict]:
    """Load signals from cache if fresh enough."""
    with _LOCK:
        age = _get_cache_age(_SIGNALS_CACHE_FILE)
        if age is not None and age <= max_age_seconds:
            data = _read_json(_SIGNALS_CACHE_FILE)
            if data and "signals" in data:
                logger.info(f"Signals loaded from cache (age: {age:.0f}s)")
                return data["signals"]
        return None


def load_signals_fallback() -> Dict:
    """Load signals from cache or return defaults."""
    cached = load_signals(max_age_seconds=float("inf"))
    if cached:
        return cached
    logger.warning("Using DEFAULT signals (no cache)")
    return DEFAULT_SIGNALS.copy()


def save_macro_data(macro: Dict) -> None:
    """Save macro indicators to cache."""
    with _LOCK:
        data = {
            "macro": macro,
            "cached_at": datetime.now().isoformat(timespec="seconds"),
        }
        _write_json(_MACRO_CACHE_FILE, data)
        logger.info("Macro data saved to cache")


def load_macro_data(max_age_seconds: float = 43200) -> Optional[Dict]:
    """Load macro data from cache (valid for 12 hours)."""
    with _LOCK:
        age = _get_cache_age(_MACRO_CACHE_FILE)
        if age is not None and age <= max_age_seconds:
            data = _read_json(_MACRO_CACHE_FILE)
            if data and "macro" in data:
                logger.info(f"Macro data loaded from cache (age: {age:.0f}s)")
                return data["macro"]
        return None


def load_macro_fallback() -> Dict:
    """Load macro data from cache or return defaults."""
    cached = load_macro_data(max_age_seconds=float("inf"))
    if cached:
        return cached
    logger.warning("Using DEFAULT macro data (no cache)")
    return DEFAULT_MACRO.copy()


def clear_all_cache() -> None:
    """Clear all cache files."""
    with _LOCK:
        for f in [_MARKET_CACHE_FILE, _SIGNALS_CACHE_FILE, _MACRO_CACHE_FILE]:
            try:
                if f.exists():
                    f.unlink()
                    logger.info(f"Cleared cache: {f}")
            except OSError as e:
                logger.error(f"Failed to clear {f}: {e}")
