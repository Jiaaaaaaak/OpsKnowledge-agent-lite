"""
Thin wrapper around the FastAPI backend.

Backend URL 由 BACKEND_URL 環境變數提供；本地預設 http://localhost:8000，
docker-compose 內注入 http://backend:8000。所有方法回傳 dict / list / None，
連線失敗或 HTTP error 一律 raise APIError，讓 UI 一次 catch。
"""
from __future__ import annotations

import os
from typing import Any

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8000").rstrip("/")
DEFAULT_TIMEOUT = 60  # incident analysis 在真 LLM 下可能需要時間


class APIError(RuntimeError):
    """Backend 呼叫失敗（連線錯誤 / 4xx / 5xx）。包含 status_code 與 detail。"""

    def __init__(self, message: str, status_code: int | None = None, detail: Any = None) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.detail = detail


def _request(method: str, path: str, **kwargs) -> Any:
    url = f"{BACKEND_URL}{path}"
    timeout = kwargs.pop("timeout", DEFAULT_TIMEOUT)
    try:
        resp = requests.request(method, url, timeout=timeout, **kwargs)
    except requests.RequestException as exc:
        raise APIError(f"無法連線到後端 ({url}): {exc}") from exc
    if not resp.ok:
        detail: Any
        try:
            detail = resp.json().get("detail", resp.text)
        except ValueError:
            detail = resp.text
        raise APIError(f"後端回應 {resp.status_code}: {detail}", status_code=resp.status_code, detail=detail)
    if resp.status_code == 204 or not resp.content:
        return None
    try:
        return resp.json()
    except ValueError:
        return resp.text


# ── Projects ─────────────────────────────────────────────────


def list_projects() -> list[dict]:
    return _request("GET", "/projects/") or []


def create_project(name: str, description: str | None = None) -> dict:
    payload = {"name": name}
    if description:
        payload["description"] = description
    return _request("POST", "/projects/", json=payload)


# ── Upload ───────────────────────────────────────────────────


def upload_document(project_id: str, filename: str, content: bytes, mimetype: str) -> dict:
    files = {"file": (filename, content, mimetype)}
    return _request("POST", f"/projects/{project_id}/upload/documents", files=files, timeout=180)


def upload_tickets(project_id: str, filename: str, content: bytes, mimetype: str) -> dict:
    files = {"file": (filename, content, mimetype)}
    return _request("POST", f"/projects/{project_id}/upload/tickets", files=files, timeout=120)


# ── Chat & Analysis ──────────────────────────────────────────


def chat(project_id: str, question: str, top_k: int = 5) -> dict:
    return _request("POST", f"/projects/{project_id}/chat", json={"question": question, "top_k": top_k})


def analyze_incidents(project_id: str) -> dict:
    return _request("POST", f"/projects/{project_id}/analyze/incidents", timeout=600)


# ── Dashboard / Observability ────────────────────────────────


def get_dashboard(project_id: str) -> dict:
    return _request("GET", f"/projects/{project_id}/dashboard")


def list_agent_runs(project_id: str, limit: int = 50) -> list[dict]:
    return _request("GET", f"/projects/{project_id}/agent-runs", params={"limit": limit}) or []


def list_tool_calls(agent_run_id: str) -> list[dict]:
    return _request("GET", f"/agent-runs/{agent_run_id}/tool-calls") or []
