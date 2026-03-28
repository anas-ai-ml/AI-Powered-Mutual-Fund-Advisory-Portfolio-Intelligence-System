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
