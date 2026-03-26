"""
ai_layer/data_ingestion/macro_data.py
─────────────────────────────────────
Fetches macroeconomic indicators for India from real public sources:

  Source 1  — FRED (St. Louis Fed): CPI India YoY % change
              URL: https://fred.stlouisfed.org/graph/fredgraph.csv?id=INDCPIALLMINMEI
              No API key required. Returns a CSV with date,value columns.

  Source 2  — FBIL (Financial Benchmarks India): Repo rate
              URL: https://fbil.org.in/sbr/  — public page, scrape the rate.
              Fallback: hardcoded last-known RBI repo rate.

  Source 3  — yfinance: 10-year India Government Bond Yield
              Ticker: ^IN10Y (if available) or FRED INDIRLTLT01STM.

All sources are wrapped in try/except with sensible fallback values so
a network outage never crashes the dashboard.
"""

import csv
import io
import logging
import re
import time
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

import requests
import yfinance as yf

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
INITIAL_BACKOFF = 2

# ── Constants & fallback values ──────────────────────────────────────────────

# FRED public CSV endpoints (no API key needed)
_FRED_CPI_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    "?id=INDCPIALLMINMEI"  # India CPI All Items (monthly index level)
)
_FRED_BOND_URL = (
    "https://fred.stlouisfed.org/graph/fredgraph.csv"
    "?id=INDIRLTLT01STM"  # India Long-Term Government Bond Yield %
)

# FBIL repo rate page (public)
_FBIL_REPO_URL = "https://fbil.org.in/sbr/"

_REQUEST_TIMEOUT = 10
_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}

# Last-known fallback values (India, early 2026)
_FALLBACKS = {
    "cpi_yoy_pct": 6.0,  # ~6% general inflation
    "repo_rate_pct": 6.5,  # RBI repo rate 6.5%
    "bond_yield_pct": 7.1,  # 10Y Gsec yield ~7.1%
}


# ── Helpers ──────────────────────────────────────────────────────────────────


def _retry_request(
    url: str, max_retries: int = MAX_RETRIES
) -> Optional[requests.Response]:
    """Make HTTP request with retry and exponential backoff."""
    last_error = None
    for attempt in range(max_retries):
        try:
            resp = requests.get(url, timeout=_REQUEST_TIMEOUT, headers=_HEADERS)
            resp.raise_for_status()
            return resp
        except Exception as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = INITIAL_BACKOFF * (2**attempt)
                logger.warning(
                    f"Request to {url} failed (attempt {attempt + 1}): {e}. Retrying in {wait_time}s..."
                )
                time.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed for {url}: {e}")
    return None


def _fetch_fred_last_value(url: str) -> Optional[float]:
    """
    Download a FRED CSV and return the most recent non-null value.
    FRED CSVs have two columns: DATE, VALUE (with '.' for missing).
    """
    resp = _retry_request(url)
    if resp is None:
        return None
    try:
        reader = csv.DictReader(io.StringIO(resp.text))
        rows = [r for r in reader if r.get("VALUE", ".") not in (".", "", None)]
        if not rows:
            return None
        return float(rows[-1]["VALUE"])
    except Exception as exc:
        logger.warning("macro_data: FRED parse failed (%s): %s", url, exc)
        return None
        return float(rows[-1]["VALUE"])
    except Exception as exc:
        logger.warning("macro_data: FRED fetch failed (%s): %s", url, exc)
        return None


def _compute_cpi_yoy() -> Optional[float]:
    """
    Compute YoY inflation from FRED India CPI index levels.
    Returns the % change between the latest month and 12 months prior.
    """
    resp = _retry_request(_FRED_CPI_URL)
    if resp is None:
        return None
    try:
        reader = list(csv.DictReader(io.StringIO(resp.text)))
        valid = [
            {"date": r["DATE"], "value": float(r["VALUE"])}
            for r in reader
            if r.get("VALUE", ".") not in (".", "", None)
        ]
        if len(valid) < 13:
            return None

        latest = valid[-1]["value"]
        year_ago = valid[-13]["value"]
        if year_ago == 0:
            return None
        return round(((latest - year_ago) / year_ago) * 100, 2)
    except Exception as exc:
        logger.warning("macro_data: CPI YoY compute failed: %s", exc)
        return None


def _fetch_repo_rate() -> Optional[float]:
    """
    Scrape RBI repo rate from FBIL public page.
    Falls back to last-known value if scraping fails.
    """
    resp = _retry_request(_FBIL_REPO_URL)
    if resp is None:
        return None
    try:
        matches = re.findall(r"(\d+\.?\d*)\s*%", resp.text)
        candidates = [float(m) for m in matches if 4.0 <= float(m) <= 10.0]
        if candidates:
            return round(candidates[0], 2)
        return None
    except Exception as exc:
        logger.warning("macro_data: Repo rate scrape failed: %s", exc)
        return None


def safe_fetch(fetch_func, default_value):
    try:
        val = fetch_func()
        if val is None:
            return default_value
        return val
    except Exception as e:
        print(f"[WARNING] Data fetch failed: {e}")
        return default_value


def _build_metric_payload(
    value: float, source: str, fetched_at: str, is_fallback: bool
) -> Dict[str, Any]:
    return {
        "value": value,
        "source": source,
        "fetched_at": fetched_at,
        "is_fallback": is_fallback,
    }

def _fetch_bond_yield() -> Optional[float]:
    """
    Fetch 10-year India government bond yield.
    Tries yfinance ticker '^INDIAVIX', then falls back to FRED CSV.
    """
    # Try yfinance first (faster)
    try:
        ticker = yf.Ticker("^INDIAVIX")
        hist = ticker.history(period="5d")
        if not hist.empty:
            return round(float(hist["Close"].dropna().iloc[-1]), 2)
    except Exception:
        pass  # Fall through to FRED

    val = _fetch_fred_last_value(_FRED_BOND_URL)
    if val is not None:
        return round(val, 2)
    return None

def get_macro_indicators(use_cache: bool = True) -> Dict[str, Any]:
    """
    Fetch real-time macroeconomic indicators for India.

    Parameters
    ----------
    use_cache : bool
        If True, try cache first before live fetch (default True).

    Returns
    -------
    dict
        ``cpi_yoy_pct``      – CPI India YoY % change (e.g. 6.1)
        ``repo_rate_pct``    – RBI repo rate in % (e.g. 6.5)
        ``bond_yield_pct``   – 10Y Gsec yield in % (e.g. 7.1)
        ``inflation_trend``  – "rising" | "stable" | "falling"
        ``rate_trend``       – "rising" | "stable" | "falling"
        ``source``           – "live" | "partial" | "fallback"
        ``fetched_at``       – ISO timestamp
    """
    if use_cache:
        try:
            from data.cache.cache_manager import load_macro_data, save_macro_data

            cached = load_macro_data(max_age_seconds=43200)
            if cached:
                logger.info("Using cached macro data")
                return cached
        except Exception as e:
            logger.warning(f"Macro cache read failed: {e}")

    results: Dict[str, Any] = {}
    live_count = 0
    fetched_at = datetime.now().isoformat(timespec="seconds")
    data_points: Dict[str, Dict[str, Any]] = {}

    try:
        cpi_live = _compute_cpi_yoy()
    except Exception:
        cpi_live = None
    cpi = _FALLBACKS["cpi_yoy_pct"] if cpi_live is None else cpi_live
    cpi_is_fallback = cpi_live is None
    if not cpi_is_fallback:
        live_count += 1
    data_points["cpi_yoy_pct"] = _build_metric_payload(
        cpi,
        "FRED" if not cpi_is_fallback else "fallback",
        fetched_at,
        cpi_is_fallback,
    )
    results["cpi_yoy_pct"] = cpi

    try:
        repo_live = _fetch_repo_rate()
    except Exception:
        repo_live = None
    repo = _FALLBACKS["repo_rate_pct"] if repo_live is None else repo_live
    repo_is_fallback = repo_live is None
    if not repo_is_fallback:
        live_count += 1
    data_points["repo_rate_pct"] = _build_metric_payload(
        repo,
        "RBI" if not repo_is_fallback else "fallback",
        fetched_at,
        repo_is_fallback,
    )
    results["repo_rate_pct"] = repo

    try:
        bond_live = _fetch_bond_yield()
    except Exception:
        bond_live = None
    bond = _FALLBACKS["bond_yield_pct"] if bond_live is None else bond_live
    bond_is_fallback = bond_live is None
    if not bond_is_fallback:
        live_count += 1
    data_points["bond_yield_pct"] = _build_metric_payload(
        bond,
        "FRED/yfinance" if not bond_is_fallback else "fallback",
        fetched_at,
        bond_is_fallback,
    )
    results["bond_yield_pct"] = bond

    cpi_val = results["cpi_yoy_pct"]
    if cpi_val > 6.5:
        results["inflation_trend"] = "rising"
    elif cpi_val < 4.5:
        results["inflation_trend"] = "falling"
    else:
        results["inflation_trend"] = "stable"

    repo_val = results["repo_rate_pct"]
    if repo_val > 6.5:
        results["rate_trend"] = "rising"
    elif repo_val < 5.5:
        results["rate_trend"] = "falling"
    else:
        results["rate_trend"] = "stable"

    if live_count == 3:
        results["source"] = "live"
    elif live_count > 0:
        results["source"] = "partial"
    else:
        results["source"] = "fallback"

    results["fetched_at"] = fetched_at
    results["data_points"] = data_points
    logger.info("macro_data: indicators ready — source=%s", results["source"])

    try:
        from data.cache.cache_manager import save_macro_data

        save_macro_data(results)
    except Exception as e:
        logger.warning(f"Macro cache save failed: {e}")

    return results


# ── Fallback helpers ──────────────────────────────────────────────────────────

_MACRO_CACHE_FILE = "ai_layer/data/cache/macro_cache.json"


def macro_fallback() -> Dict[str, Any]:
    """
    Return stable synthetic macro values.
    Used as the last resort when all live and cached sources fail.
    """
    return {
        "cpi_yoy_pct": _FALLBACKS["cpi_yoy_pct"],
        "repo_rate_pct": _FALLBACKS["repo_rate_pct"],
        "bond_yield_pct": _FALLBACKS["bond_yield_pct"],
        "inflation_trend": "stable",
        "rate_trend": "stable",
        "source": "fallback",
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
        "data_points": {
            "cpi_yoy_pct": _build_metric_payload(
                _FALLBACKS["cpi_yoy_pct"], "fallback", datetime.now().isoformat(timespec="seconds"), True
            ),
            "repo_rate_pct": _build_metric_payload(
                _FALLBACKS["repo_rate_pct"], "fallback", datetime.now().isoformat(timespec="seconds"), True
            ),
            "bond_yield_pct": _build_metric_payload(
                _FALLBACKS["bond_yield_pct"], "fallback", datetime.now().isoformat(timespec="seconds"), True
            ),
        },
    }


def get_macro_indicators_safe(use_cache: bool = True) -> Dict[str, Any]:
    """
    Fault-tolerant wrapper around get_macro_indicators.

    Fallback hierarchy:
      1. Live fetch (FRED, FBIL, yfinance)
      2. Cache file at _MACRO_CACHE_FILE (if exists and readable)
      3. macro_fallback() — hardcoded stable synthetic values

    Never raises. Always returns a valid dict.
    """
    try:
        return get_macro_indicators(use_cache=use_cache)
    except Exception as e:
        logger.warning("macro_data: live fetch failed entirely: %s", e)

    # Try local JSON cache file as secondary fallback
    try:
        import json
        import os

        if os.path.exists(_MACRO_CACHE_FILE):
            with open(_MACRO_CACHE_FILE, "r") as f:
                cached = json.load(f)
            if cached:
                cached["source"] = "cache_file"
                logger.info("macro_data: loaded from cache file %s", _MACRO_CACHE_FILE)
                return cached
    except Exception as cache_err:
        logger.warning("macro_data: cache file load failed: %s", cache_err)

    logger.warning("macro_data: all sources failed — using synthetic fallback")
    return macro_fallback()
