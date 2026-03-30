"""
backend/services/ai_note_extractor.py
──────────────────────────────────────
Deterministic regex/keyword transcript extraction service.
Extracts structured advisory inputs from meeting notes/transcripts.
AI-free for PoC — extensible to LLM call by replacing extract_from_transcript().
"""
import re
from typing import Any, Dict, List, Optional


_RISK_KEYWORDS = {
    "conservative": ["safe", "conservative", "capital protection", "low risk", "fd", "fixed deposit", "stable"],
    "moderate": ["moderate", "balanced", "medium risk", "some risk"],
    "aggressive": ["aggressive", "high risk", "growth", "maximum returns", "equity heavy"],
}

_HOLDING_KEYWORDS = ["mutual fund", "sip", "fd", "fixed deposit", "nps", "ppf", "epf", "gold", "real estate", "stocks", "shares", "equity", "debt fund", "liquid fund", "elss", "ulip"]

_PRODUCT_KEYWORDS = ["flexi cap", "large cap", "mid cap", "small cap", "elss", "debt", "liquid", "hybrid", "index fund", "nfo", "sip", "lumpsum", "stp", "swp"]


def _confidence(value: Any, method: str) -> str:
    if method == "numeric_with_unit":
        return "high"
    if method == "numeric_only":
        return "medium"
    return "low"


def _extract_age(text: str) -> tuple[Optional[int], str]:
    patterns = [
        (r"\b(?:i am|age[d]?|aged|currently)\s+(\d{1,2})\b", "numeric_with_unit"),
        (r"\b(\d{1,2})\s*(?:years?\s*old|yr\s*old)\b", "numeric_with_unit"),
        (r"\bage[:\s]+(\d{1,2})\b", "numeric_with_unit"),
        (r"\b(\d{1,2})\s*(?:years?|yr)\b", "numeric_only"),
    ]
    for pattern, method in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            age = int(match.group(1))
            if 18 <= age <= 85:
                return age, method
    return None, "not_found"


def _extract_sip(text: str) -> tuple[Optional[float], str]:
    patterns = [
        (r"₹\s*([\d,]+)\s*(?:per\s*month|monthly|sip)", "numeric_with_unit"),
        (r"([\d,]+)\s*(?:rupees?|rs\.?|inr)?\s*(?:per\s*month|monthly|sip)", "numeric_with_unit"),
        (r"sip\s*(?:of|for|at)?\s*₹?\s*([\d,]+)", "numeric_with_unit"),
        (r"\b(\d+)k\s*(?:sip|monthly|per\s*month)\b", "numeric_with_unit"),
    ]
    for pattern, method in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                amount = float(raw)
                if "k" in match.group(0).lower() and amount < 1000:
                    amount *= 1000
                if 500 <= amount <= 500000:
                    return amount, method
            except ValueError:
                continue
    return None, "not_found"


def _extract_horizon(text: str) -> tuple[Optional[int], str]:
    patterns = [
        (r"(\d+)\s*(?:year|yr)s?\s*(?:horizon|goal|target|investment|away|plan)", "numeric_with_unit"),
        (r"(?:next|in|over|for)\s+(\d+)\s*(?:year|yr)s?", "numeric_with_unit"),
        (r"(\d+)\s*(?:year|yr)s?\s*(?:from now|later|hence)", "numeric_with_unit"),
        (r"\b(\d+)\s*(?:year|yr)s?\b", "numeric_only"),
    ]
    for pattern, method in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            years = int(match.group(1))
            if 1 <= years <= 40:
                return years, method
    return None, "not_found"


def _extract_risk_cues(text: str) -> List[str]:
    found = []
    text_lower = text.lower()
    for level, keywords in _RISK_KEYWORDS.items():
        for kw in keywords:
            if kw in text_lower:
                found.append(f"{level}: {kw}")
    return list(dict.fromkeys(found))


def _extract_holdings(text: str) -> List[str]:
    text_lower = text.lower()
    return [kw for kw in _HOLDING_KEYWORDS if kw in text_lower]


def _extract_product_interest(text: str) -> List[str]:
    text_lower = text.lower()
    return [kw for kw in _PRODUCT_KEYWORDS if kw in text_lower]


def _extract_monthly_income(text: str) -> tuple[Optional[float], str]:
    patterns = [
        (r"(?:income|salary|earning[s]?|ctc|take\s*home)\s*(?:is|of|around|about)?\s*₹?\s*([\d,]+)\s*(?:per\s*month|monthly|pm|\/month|lakh|l|k)?", "numeric_with_unit"),
        (r"₹\s*([\d,]+)\s*(?:per\s*month|monthly|pm|\/month)", "numeric_with_unit"),
    ]
    for pattern, method in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            raw = match.group(1).replace(",", "")
            try:
                amount = float(raw)
                suffix = match.group(0).lower()
                if "lakh" in suffix or " l" in suffix:
                    amount *= 100000
                elif "k" in suffix and amount < 1000:
                    amount *= 1000
                if 5000 <= amount <= 5000000:
                    return amount, method
            except ValueError:
                continue
    return None, "not_found"


def _extract_occupation(text: str) -> tuple[Optional[str], str]:
    patterns = [
        r"\b(?:i am|i'm|works? as|working as|profession[al]?|job)\s+(?:a\s+|an\s+)?([a-zA-Z\s]+?)(?:\.|,|\band\b|\bwith\b)",
        r"\b(salaried|self[\s-]?employed|businessman|doctor|engineer|lawyer|teacher|consultant|freelancer|government employee|private employee|retired)\b",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            occ = match.group(1).strip().title()
            if 2 < len(occ) < 50:
                return occ, "keyword"
    return None, "not_found"


def _extract_city(text: str) -> tuple[Optional[str], str]:
    pattern = r"\b(?:from|in|based in|located in|living in|residing in)\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)?)\b"
    match = re.search(pattern, text)
    if match:
        city = match.group(1).strip()
        if 2 < len(city) < 50:
            return city, "keyword"
    return None, "not_found"


def _build_summary(extractions: Dict[str, Any]) -> str:
    parts = []
    if extractions.get("age"):
        parts.append(f"Client aged {extractions['age']}")
    if extractions.get("occupation"):
        parts.append(f"occupation: {extractions['occupation']}")
    if extractions.get("city"):
        parts.append(f"based in {extractions['city']}")
    if extractions.get("monthly_income"):
        parts.append(f"monthly income ₹{extractions['monthly_income']:,.0f}")
    if extractions.get("monthly_sip_amount"):
        parts.append(f"SIP target ₹{extractions['monthly_sip_amount']:,.0f}/month")
    if extractions.get("horizon_years"):
        parts.append(f"investment horizon {extractions['horizon_years']} years")
    if extractions.get("risk_cues"):
        parts.append(f"risk cues: {', '.join(extractions['risk_cues'][:3])}")
    if extractions.get("current_holdings"):
        parts.append(f"mentions {', '.join(extractions['current_holdings'][:3])}")
    if extractions.get("product_interest"):
        parts.append(f"interested in {', '.join(extractions['product_interest'][:3])}")
    if not parts:
        return "No structured information could be extracted from the transcript."
    return "Advisory note summary: " + "; ".join(parts) + "."


def extract_from_transcript(raw_transcript: str) -> Dict[str, Any]:
    """
    Extract structured advisory inputs from a meeting transcript.
    Returns extractions dict, confidence_flags dict, and ai_summary string.
    All fields are optional — None means not found.
    Confidence: 'high' = direct numeric+unit, 'medium' = numeric only, 'low' = keyword match.
    """
    text = str(raw_transcript or "")

    age, age_method = _extract_age(text)
    sip, sip_method = _extract_sip(text)
    horizon, horizon_method = _extract_horizon(text)
    income, income_method = _extract_monthly_income(text)
    occupation, occ_method = _extract_occupation(text)
    city, city_method = _extract_city(text)
    risk_cues = _extract_risk_cues(text)
    holdings = _extract_holdings(text)
    products = _extract_product_interest(text)

    extractions: Dict[str, Any] = {
        "age": age,
        "monthly_sip_amount": sip,
        "horizon_years": horizon,
        "monthly_income": income,
        "occupation": occupation,
        "city": city,
        "risk_cues": risk_cues if risk_cues else None,
        "current_holdings": holdings if holdings else None,
        "product_interest": products if products else None,
    }

    confidence_flags: Dict[str, str] = {
        "age": _confidence(age, age_method) if age else "not_found",
        "monthly_sip_amount": _confidence(sip, sip_method) if sip else "not_found",
        "horizon_years": _confidence(horizon, horizon_method) if horizon else "not_found",
        "monthly_income": _confidence(income, income_method) if income else "not_found",
        "occupation": _confidence(occupation, occ_method) if occupation else "not_found",
        "city": _confidence(city, city_method) if city else "not_found",
        "risk_cues": "low" if risk_cues else "not_found",
        "current_holdings": "low" if holdings else "not_found",
        "product_interest": "low" if products else "not_found",
    }

    ai_summary = _build_summary(extractions)

    return {
        "extractions": extractions,
        "confidence_flags": confidence_flags,
        "ai_summary": ai_summary,
    }
