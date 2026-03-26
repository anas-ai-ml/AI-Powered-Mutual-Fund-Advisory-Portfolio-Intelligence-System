import json
from pathlib import Path
from typing import Any, Dict


_FIXTURE_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "fixtures" / "benchmark_returns.json"
)

_CATEGORY_BENCHMARKS = {
    "large cap": "Nifty 50 TRI",
    "flexi": "Nifty 50 TRI",
    "hybrid": "Nifty 50 TRI",
    "mid cap": "Nifty Midcap 150 TRI",
    "small cap": "Nifty Midcap 150 TRI",
    "sectoral": "Nifty Midcap 150 TRI",
    "debt": "CRISIL Short Term Bond Index",
    "liquid": "CRISIL Short Term Bond Index",
    "gold": "Gold Price Index",
    "commodity": "Gold Price Index"
}


def load_benchmark_fixture() -> Dict[str, Dict[str, float]]:
    with open(_FIXTURE_PATH, "r", encoding="utf-8") as fh:
        return json.load(fh)


def benchmark_for_category(category: str) -> str:
    normalized = str(category or "").lower()
    for key, benchmark in _CATEGORY_BENCHMARKS.items():
        if key in normalized:
            return benchmark
    return "Nifty 50 TRI"


def benchmark_metrics_for_category(category: str) -> Dict[str, Any]:
    fixture = load_benchmark_fixture()
    benchmark_name = benchmark_for_category(category)
    metrics = fixture.get(benchmark_name, {})
    return {"benchmark_index": benchmark_name, **metrics}


def enrich_with_benchmark_metrics(fund: Dict[str, Any]) -> Dict[str, Any]:
    benchmark = benchmark_metrics_for_category(fund.get("category", ""))
    fund_1y = float(fund.get("1y", 0.0))
    fund_3y = float(fund.get("3y", 0.0))
    benchmark_1y = float(benchmark.get("1y_return", 0.0))
    benchmark_3y = float(benchmark.get("3y_return", 0.0))
    fund_volatility = float(fund.get("volatility", 0.0))
    benchmark_volatility = float(benchmark.get("volatility", 0.0))
    tracking_error = max(abs(fund_volatility - benchmark_volatility), 0.01)
    alpha_3y = fund_3y - benchmark_3y

    return {
        **fund,
        "benchmark_index": benchmark["benchmark_index"],
        "benchmark_1y_return": round(benchmark_1y, 2),
        "benchmark_3y_return": round(benchmark_3y, 2),
        "alpha_1y": round(fund_1y - benchmark_1y, 2),
        "alpha_3y": round(alpha_3y, 2),
        "information_ratio": round(alpha_3y / tracking_error, 2),
        "tracking_error": round(tracking_error, 2),
    }


def infer_fund_type(name: str) -> str:
    normalized = str(name or "").lower()
    if " etf" in normalized or normalized.endswith("etf") or "exchange traded fund" in normalized:
        return "ETF"
    return "Mutual Fund"
