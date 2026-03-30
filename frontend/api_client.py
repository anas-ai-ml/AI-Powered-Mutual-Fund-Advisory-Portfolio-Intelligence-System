import json
import os
from pathlib import Path
from typing import Any

import httpx
from dotenv import load_dotenv


load_dotenv(Path(__file__).resolve().parent.parent / ".env")

API_BASE_URL = os.getenv("BACKEND_API_URL", "http://127.0.0.1:8000").rstrip("/")


class APIClientError(RuntimeError):
    """Raised when the backend API returns an error."""


def _normalize_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): _normalize_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_normalize_json(item) for item in value]
    if hasattr(value, "item") and callable(getattr(value, "item")):
        try:
            return value.item()
        except Exception:
            pass
    if hasattr(value, "isoformat") and callable(getattr(value, "isoformat")):
        try:
            return value.isoformat()
        except Exception:
            pass
    return value


def _request(method: str, path: str, *, token: str | None = None, payload: Any | None = None) -> Any:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    try:
        response = httpx.request(
            method,
            f"{API_BASE_URL}{path}",
            headers=headers,
            json=_normalize_json(payload) if payload is not None else None,
            timeout=30.0,
        )
    except httpx.HTTPError as exc:
        raise APIClientError(f"Unable to reach backend API at {API_BASE_URL}: {exc}") from exc

    if response.is_error:
        try:
            detail = response.json().get("detail")
        except (ValueError, json.JSONDecodeError, AttributeError):
            detail = response.text
        raise APIClientError(detail or f"API request failed with status {response.status_code}")

    if not response.content:
        return None
    return response.json()


def login_advisor(email: str, password: str) -> dict[str, Any]:
    return _request(
        "POST",
        "/auth/login",
        payload={"email": email.strip(), "password": password},
    )


def register_advisor(email: str, password: str, name: str, role: str = "advisor") -> dict[str, Any]:
    return _request(
        "POST",
        "/auth/register",
        payload={
            "email": email.strip(),
            "password": password,
            "name": name.strip(),
            "role": role,
        },
    )


def get_current_advisor(token: str) -> dict[str, Any]:
    return _request("GET", "/auth/me", token=token)


def list_clients(token: str) -> list[dict[str, Any]]:
    return _request("GET", "/clients/", token=token)


def get_client_record(token: str, client_id: int) -> dict[str, Any]:
    return _request("GET", f"/clients/{client_id}", token=token)


def create_client_record(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", "/clients/", token=token, payload=payload)


def update_client_record(token: str, client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("PUT", f"/clients/{client_id}", token=token, payload=payload)


def save_client_analysis_record(
    token: str,
    client_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/clients/{client_id}/save-analysis",
        token=token,
        payload=payload,
    )


def get_client_audit_trail(token: str, client_id: int) -> list[dict[str, Any]]:
    return _request("GET", f"/clients/{client_id}/audit-trail", token=token)


def create_client_audit_log(
    token: str,
    client_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    return _request("POST", f"/clients/{client_id}/audit-log", token=token, payload=payload)


# ── Meeting Notes ────────────────────────────────────────────────────────────

def create_meeting_note(token: str, client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", f"/clients/{client_id}/meeting-notes", token=token, payload=payload)


def list_meeting_notes(token: str, client_id: int) -> list[dict[str, Any]]:
    return _request("GET", f"/clients/{client_id}/meeting-notes", token=token) or []


def apply_meeting_note_to_profile(token: str, note_id: int) -> dict[str, Any]:
    return _request("POST", f"/meeting-notes/{note_id}/apply-to-profile", token=token)


# ── Proposals (versioned) ─────────────────────────────────────────────────────

def create_proposal_draft(token: str, client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", f"/clients/{client_id}/proposals", token=token, payload=payload)


def list_proposals(token: str, client_id: int) -> list[dict[str, Any]]:
    return _request("GET", f"/clients/{client_id}/proposals", token=token) or []


def approve_proposal(token: str, client_id: int, proposal_id: int) -> dict[str, Any]:
    return _request("POST", f"/clients/{client_id}/proposals/{proposal_id}/approve", token=token)


def issue_proposal_report(
    token: str, client_id: int, proposal_id: int, payload: dict[str, Any]
) -> dict[str, Any]:
    return _request(
        "POST",
        f"/clients/{client_id}/proposals/{proposal_id}/issue",
        token=token,
        payload=payload,
    )


def list_issued_reports(token: str, client_id: int) -> list[dict[str, Any]]:
    return _request("GET", f"/clients/{client_id}/issued-reports", token=token) or []


# ── AI Extraction ─────────────────────────────────────────────────────────────

def extract_meeting_notes_ai(token: str, raw_transcript: str) -> dict[str, Any]:
    return _request("POST", "/ai/extract-meeting-notes", token=token, payload={"raw_transcript": raw_transcript})


# ── Global Audit Trail ────────────────────────────────────────────────────────

def get_global_audit_trail(token: str, limit: int = 20) -> list[dict[str, Any]]:
    return _request("GET", f"/audit-trail?limit={limit}", token=token) or []


# ── Proposal counts ───────────────────────────────────────────────────────────

def get_proposal_counts(token: str) -> dict[str, int]:
    """Returns {client_id_str: proposal_count} for all accessible clients."""
    return _request("GET", "/clients/proposal-counts", token=token) or {}


# ── Overrides ─────────────────────────────────────────────────────────────────

def create_override(token: str, client_id: int, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("POST", f"/clients/{client_id}/overrides", token=token, payload=payload)


def list_overrides(token: str, client_id: int, status: str | None = None) -> list[dict[str, Any]]:
    url = f"/clients/{client_id}/overrides"
    if status:
        url += f"?status={status}"
    return _request("GET", url, token=token) or []


def approve_override(token: str, client_id: int, override_id: int) -> dict[str, Any]:
    return _request("POST", f"/clients/{client_id}/overrides/{override_id}/approve", token=token)


def reject_override(token: str, client_id: int, override_id: int, reason: str = "") -> dict[str, Any]:
    return _request("POST", f"/clients/{client_id}/overrides/{override_id}/reject", token=token, payload={"reason": reason})


# ── Advisor Profile ───────────────────────────────────────────────────────────

def get_advisor_profile(token: str) -> dict[str, Any]:
    return _request("GET", "/auth/me/profile", token=token)


def update_advisor_profile(token: str, payload: dict[str, Any]) -> dict[str, Any]:
    return _request("PUT", "/auth/me/profile", token=token, payload=payload)


# ── Portal ────────────────────────────────────────────────────────────────────

def portal_get_client_reports(client_id: int) -> dict[str, Any]:
    return _request("GET", f"/portal/client/{client_id}/reports") or {}
