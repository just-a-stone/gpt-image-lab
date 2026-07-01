from __future__ import annotations

import os

from fastapi import HTTPException

_TRUTHY = {"1", "true", "yes", "on"}
DELETION_DISABLED_MESSAGE = "管理员已禁止删除功能"


def deletion_disabled() -> bool:
    return os.environ.get("WEBUI_DISABLE_DELETION", "").strip().lower() in _TRUTHY


def ensure_deletion_allowed() -> None:
    if deletion_disabled():
        raise HTTPException(status_code=403, detail=DELETION_DISABLED_MESSAGE)


def byok_base_url_locked() -> bool:
    return os.environ.get("WEBUI_LOCK_BYOK_BASE_URL", "").strip().lower() in _TRUTHY
