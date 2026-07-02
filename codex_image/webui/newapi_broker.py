from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from typing import Any

from . import feature_flags
from .newapi_securecookie import decode_session_cookie


def _http_json(
    method: str,
    url: str,
    *,
    session_cookie: str,
    user_id: int | None = None,
    body: dict[str, Any] | None = None,
    timeout: float = 15.0,
) -> dict[str, Any] | None:
    headers = {
        "Cookie": f"session={session_cookie}",
        "Accept": "application/json",
        "User-Agent": "feiyang-lab-newapi-broker/1.0",
    }
    if user_id is not None:
        headers["New-Api-User"] = str(user_id)
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = response.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    if not payload:
        return None
    try:
        parsed = json.loads(payload.decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return None
    return parsed if isinstance(parsed, dict) else None


def decode_request_session(session_cookie: str) -> dict[str, Any] | None:
    if not session_cookie:
        return None
    return decode_session_cookie(
        session_cookie,
        feature_flags.newapi_session_secret(),
        feature_flags.newapi_cookie_name(),
    )


def verify_user(session_cookie: str, candidate_id: int) -> dict[str, Any] | None:
    """Call new-api /api/user/self to authoritatively confirm identity.

    Returns the authoritative user dict {id, username, role, status, ...} on
    success, or None if the session is invalid / the candidate id is wrong.
    """
    base_url = feature_flags.newapi_base_url()
    result = _http_json(
        "GET",
        f"{base_url}/api/user/self",
        session_cookie=session_cookie,
        user_id=candidate_id,
        timeout=feature_flags.newapi_request_timeout_seconds(),
    )
    if not result or not result.get("success"):
        return None
    data = result.get("data")
    if not isinstance(data, dict):
        return None
    return data


def _list_tokens(session_cookie: str, user_id: int) -> list[dict[str, Any]]:
    base_url = feature_flags.newapi_base_url()
    timeout = feature_flags.newapi_request_timeout_seconds()
    items: list[dict[str, Any]] = []
    page = 1
    while True:
        result = _http_json(
            "GET",
            f"{base_url}/api/token/?p={page}&size=100",
            session_cookie=session_cookie,
            user_id=user_id,
            timeout=timeout,
        )
        if not result or not result.get("success"):
            break
        data = result.get("data") or {}
        page_items = data.get("items") if isinstance(data, dict) else None
        if not isinstance(page_items, list):
            break
        items.extend(item for item in page_items if isinstance(item, dict))
        total = data.get("total") if isinstance(data, dict) else 0
        try:
            total_int = int(total or 0)
        except (TypeError, ValueError):
            total_int = len(items)
        if len(items) >= total_int or not page_items:
            break
        page += 1
        if page > 50:
            break
    return items


def _create_token(session_cookie: str, user_id: int, name: str, group: str) -> None:
    base_url = feature_flags.newapi_base_url()
    _http_json(
        "POST",
        f"{base_url}/api/token/",
        session_cookie=session_cookie,
        user_id=user_id,
        body={
            "name": name,
            "group": group,
            "expired_time": -1,
            "remain_quota": 0,
            "unlimited_quota": True,
        },
        timeout=feature_flags.newapi_request_timeout_seconds(),
    )


def _fetch_token_key(session_cookie: str, user_id: int, token_id: int) -> str | None:
    base_url = feature_flags.newapi_base_url()
    result = _http_json(
        "POST",
        f"{base_url}/api/token/{token_id}/key",
        session_cookie=session_cookie,
        user_id=user_id,
        timeout=feature_flags.newapi_request_timeout_seconds(),
    )
    if not result or not result.get("success"):
        return None
    data = result.get("data")
    if isinstance(data, str) and data.strip():
        return data.strip()
    if isinstance(data, dict):
        key = str(data.get("key") or "").strip()
        if key:
            return key
    return None


_token_locks: dict[int, threading.Lock] = {}
_token_locks_guard = threading.Lock()


def _user_token_lock(user_id: int) -> threading.Lock:
    with _token_locks_guard:
        lock = _token_locks.get(user_id)
        if lock is None:
            lock = threading.Lock()
            _token_locks[user_id] = lock
        return lock


def ensure_api_token(session_cookie: str, user_id: int) -> str | None:
    """Find (by name+group) or create the dedicated WebUI token, return its key."""
    with _user_token_lock(user_id):
        name = feature_flags.newapi_token_name()
        group = feature_flags.newapi_token_group()

        def matches(item: dict[str, Any]) -> bool:
            return str(item.get("name") or "") == name and str(item.get("group") or "") == group

        tokens = _list_tokens(session_cookie, user_id)
        token_id = None
        for item in tokens:
            if matches(item):
                token_id = item.get("id")
                break
        if token_id is None:
            _create_token(session_cookie, user_id, name, group)
            tokens = _list_tokens(session_cookie, user_id)
            for item in tokens:
                if matches(item):
                    token_id = item.get("id")
                    break
        if token_id is None:
            return None
        return _fetch_token_key(session_cookie, user_id, int(token_id))
