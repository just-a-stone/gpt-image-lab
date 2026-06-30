from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
import sqlite3
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from codex_image.webui.owner import _server_secret

SHARE_STATUS_ACTIVE = "active"
SHARE_STATUS_REVOKED = "revoked"
DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 60


def _utc_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def compute_public_author_id(owner_id: str) -> str:
    salt = _server_secret() + b":public-author"
    return "u_" + hmac.new(salt, owner_id.encode("utf-8"), hashlib.sha256).hexdigest()[:12]


def new_share_id() -> str:
    return secrets.token_urlsafe(16)


def _encode_cursor(shared_at: str, share_id: str) -> str:
    raw = json.dumps({"s": shared_at, "i": share_id}, ensure_ascii=False).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> tuple[str, str] | None:
    if not cursor:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
    except (ValueError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    shared_at = str(payload.get("s") or "")
    share_id = str(payload.get("i") or "")
    return (shared_at, share_id) if shared_at and share_id else None


class ShareStore:
    def __init__(self, db_path: Path | str) -> None:
        self.db_path = Path(db_path)
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
                    create table if not exists shared_tasks (
                        share_id         text primary key,
                        task_id          text not null unique,
                        owner            text not null,
                        public_author_id text not null,
                        shared_at        text not null,
                        show_prompt      integer not null default 1,
                        share_note       text not null default '',
                        status           text not null default 'active'
                    )
                    """
                )
                connection.execute(
                    "create index if not exists idx_shared_active "
                    "on shared_tasks(shared_at desc, share_id desc) where status = 'active'"
                )
                connection.execute(
                    "create index if not exists idx_shared_task "
                    "on shared_tasks(task_id)"
                )

    def create_share(
        self,
        *,
        task_id: str,
        owner: str,
        show_prompt: bool = True,
        share_note: str = "",
    ) -> dict[str, Any]:
        share_id = new_share_id()
        public_author_id = compute_public_author_id(owner)
        shared_at = _utc_iso()
        with closing(self._connect()) as connection:
            with connection:
                existing = connection.execute(
                    "select share_id, status from shared_tasks where task_id = ?",
                    (task_id,),
                ).fetchone()
                if existing is not None:
                    connection.execute(
                        "update shared_tasks set status = ?, owner = ?, public_author_id = ?, "
                        "shared_at = ?, show_prompt = ?, share_note = ? where task_id = ?",
                        (SHARE_STATUS_ACTIVE, owner, public_author_id, shared_at,
                         1 if show_prompt else 0, share_note, task_id),
                    )
                    share_id = str(existing["share_id"])
                else:
                    connection.execute(
                        "insert into shared_tasks "
                        "(share_id, task_id, owner, public_author_id, shared_at, show_prompt, share_note, status) "
                        "values (?, ?, ?, ?, ?, ?, ?, ?)",
                        (share_id, task_id, owner, public_author_id, shared_at,
                         1 if show_prompt else 0, share_note, SHARE_STATUS_ACTIVE),
                    )
        return {
            "share_id": share_id,
            "task_id": task_id,
            "shared_at": shared_at,
            "show_prompt": show_prompt,
            "share_note": share_note,
            "status": SHARE_STATUS_ACTIVE,
        }

    def update_share(
        self,
        *,
        task_id: str,
        owner: str,
        show_prompt: bool | None = None,
        share_note: str | None = None,
    ) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        if show_prompt is not None:
            sets.append("show_prompt = ?")
            params.append(1 if show_prompt else 0)
        if share_note is not None:
            sets.append("share_note = ?")
            params.append(share_note)
        if not sets:
            return self.get_share_by_task(task_id)
        with closing(self._connect()) as connection:
            with connection:
                row = connection.execute(
                    f"update shared_tasks set {', '.join(sets)} "
                    "where task_id = ? and owner = ? and status = ? returning *",
                    (*params, task_id, owner, SHARE_STATUS_ACTIVE),
                ).fetchone()
        return dict(row) if row else None

    def revoke_share(self, *, task_id: str, owner: str) -> bool:
        with closing(self._connect()) as connection:
            with connection:
                row = connection.execute(
                    "update shared_tasks set status = ? "
                    "where task_id = ? and owner = ? and status = ?",
                    (SHARE_STATUS_REVOKED, task_id, owner, SHARE_STATUS_ACTIVE),
                )
                return row.rowcount > 0

    def get_share_by_task(self, task_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "select * from shared_tasks where task_id = ?",
                (task_id,),
            ).fetchone()
        return dict(row) if row else None

    def get_active_share(self, share_id: str) -> dict[str, Any] | None:
        with closing(self._connect()) as connection:
            row = connection.execute(
                "select * from shared_tasks where share_id = ? and status = ?",
                (share_id, SHARE_STATUS_ACTIVE),
            ).fetchone()
        return dict(row) if row else None

    def list_active_shares(
        self,
        *,
        limit: int = DEFAULT_PAGE_SIZE,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        safe_limit = min(MAX_PAGE_SIZE, max(1, int(limit)))
        where = "status = ?"
        params: list[Any] = [SHARE_STATUS_ACTIVE]
        cursor_values = _decode_cursor(cursor)
        if cursor_values:
            cursor_shared_at, cursor_share_id = cursor_values
            where += " and (shared_at < ? or (shared_at = ? and share_id < ?))"
            params.extend([cursor_shared_at, cursor_shared_at, cursor_share_id])
        sql = (
            f"select * from shared_tasks where {where} "
            "order by shared_at desc, share_id desc limit ?"
        )
        params.append(safe_limit + 1)
        with closing(self._connect()) as connection:
            rows = connection.execute(sql, tuple(params)).fetchall()
        has_more = len(rows) > safe_limit
        page_rows = rows[:safe_limit]
        next_cursor = None
        if has_more and page_rows:
            last = page_rows[-1]
            next_cursor = _encode_cursor(str(last["shared_at"]), str(last["share_id"]))
        return {
            "items": [dict(row) for row in page_rows],
            "next_cursor": next_cursor,
        }

    def active_shared_task_ids(self, owner: str) -> set[str]:
        with closing(self._connect()) as connection:
            rows = connection.execute(
                "select task_id from shared_tasks where owner = ? and status = ?",
                (owner, SHARE_STATUS_ACTIVE),
            ).fetchall()
        return {str(row["task_id"]) for row in rows}

    def cleanup_for_task(self, task_id: str) -> None:
        with closing(self._connect()) as connection:
            with connection:
                connection.execute(
                    "update shared_tasks set status = ? where task_id = ? and status = ?",
                    (SHARE_STATUS_REVOKED, task_id, SHARE_STATUS_ACTIVE),
                )
