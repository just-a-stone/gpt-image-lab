from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import sqlite3
import sys
import time
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from fastapi import Request, Response

OWNER_COOKIE_NAME = "ownd"
OWNER_COOKIE_TTL_DAYS = 30
_OWNER_ID_PREFIX = "u_"


def _server_secret() -> bytes:
    raw = os.environ.get("WEBUI_OWNER_SECRET", "").strip()
    if raw:
        return raw.encode("utf-8")
    return secrets.token_bytes(32)


_SECRET = _server_secret()
_SECRET_FROM_ENV = bool(os.environ.get("WEBUI_OWNER_SECRET", "").strip())

if not _SECRET_FROM_ENV:
    print(
        "warning: WEBUI_OWNER_SECRET not set; owner cookies are invalid after restart. "
        "Set WEBUI_OWNER_SECRET for multi-user deployments.",
        file=sys.stderr,
    )


def secret_is_persistent() -> bool:
    return _SECRET_FROM_ENV


def compute_key_hash(api_key: str) -> str:
    return hmac.new(_SECRET, api_key.encode("utf-8"), hashlib.sha256).hexdigest()


def _new_owner_id() -> str:
    return _OWNER_ID_PREFIX + secrets.token_hex(12)


def _cookie_signature(owner_id: str, exp_ts: int) -> str:
    return hmac.new(_SECRET, f"{owner_id}.{exp_ts}".encode("utf-8"), hashlib.sha256).hexdigest()


def sign_owner_cookie(owner_id: str, *, ttl_days: int = OWNER_COOKIE_TTL_DAYS) -> str:
    exp_ts = int(time.time()) + ttl_days * 86400
    return f"{owner_id}.{exp_ts}.{_cookie_signature(owner_id, exp_ts)}"


def verify_owner_cookie(raw: str | None) -> str | None:
    if not raw:
        return None
    parts = raw.split(".")
    if len(parts) != 3:
        return None
    owner_id, exp_str, sig = parts
    try:
        exp_ts = int(exp_str)
    except ValueError:
        return None
    if exp_ts < int(time.time()):
        return None
    expected = _cookie_signature(owner_id, exp_ts)
    if not hmac.compare_digest(sig, expected):
        return None
    if not owner_id.startswith(_OWNER_ID_PREFIX):
        return None
    return owner_id


def resolve_owner(request: Request) -> str | None:
    return verify_owner_cookie(request.cookies.get(OWNER_COOKIE_NAME))


def _cookie_secure() -> bool:
    return os.environ.get("WEBUI_COOKIE_SECURE", "").strip().lower() in {"1", "true", "yes", "on"}


def set_owner_cookie(response: Response, owner_id: str) -> None:
    response.set_cookie(
        OWNER_COOKIE_NAME,
        sign_owner_cookie(owner_id),
        max_age=OWNER_COOKIE_TTL_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=_cookie_secure(),
        path="/",
    )


def clear_owner_cookie(response: Response) -> None:
    response.delete_cookie(OWNER_COOKIE_NAME, path="/")


@dataclass
class OwnerStore:
    db_path: Path

    def __post_init__(self) -> None:
        self.db_path = Path(self.db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._ensure_table()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _ensure_table(self) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    """
                    create table if not exists owner_bindings (
                        key_hash text primary key,
                        owner_id text not null unique,
                        created_at text not null default '',
                        last_seen_at text not null default ''
                    )
                    """
                )

    def get_or_create(self, key_hash: str, *, now_iso: str = "") -> str:
        now = now_iso or _utc_iso()
        with closing(self._connect()) as connection:
            with connection:
                row = connection.execute(
                    "select owner_id from owner_bindings where key_hash = ?", (key_hash,)
                ).fetchone()
                if row is not None:
                    owner_id = str(row["owner_id"])
                    connection.execute(
                        "update owner_bindings set last_seen_at = ? where key_hash = ?",
                        (now, key_hash),
                    )
                    return owner_id
                owner_id = _new_owner_id()
                connection.execute(
                    "insert into owner_bindings (key_hash, owner_id, created_at, last_seen_at) values (?, ?, ?, ?)",
                    (key_hash, owner_id, now, now),
                )
                return owner_id

    def owner_for_legacy_key(self, legacy_key: str) -> str | None:
        key_hash = compute_key_hash(legacy_key)
        with closing(self._connect()) as connection:
            row = connection.execute(
                "select owner_id from owner_bindings where key_hash = ?", (key_hash,)
            ).fetchone()
            return str(row["owner_id"]) if row is not None else None


def _utc_iso() -> str:
    from datetime import UTC, datetime
    return datetime.now(UTC).isoformat()
