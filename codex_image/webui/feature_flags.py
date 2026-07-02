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


def newapi_base_url() -> str:
    return os.environ.get("WEBUI_NEWAPI_BASE_URL", "").strip().rstrip("/")


def newapi_enabled() -> bool:
    return bool(newapi_base_url() and os.environ.get("WEBUI_NEWAPI_SESSION_SECRET", "").strip())


def newapi_session_secret() -> bytes:
    return os.environ.get("WEBUI_NEWAPI_SESSION_SECRET", "").strip().encode("utf-8")


def newapi_cookie_name() -> str:
    return os.environ.get("WEBUI_NEWAPI_COOKIE_NAME", "session").strip() or "session"


def newapi_token_name() -> str:
    return os.environ.get("WEBUI_NEWAPI_TOKEN_NAME", "feiyang-lab").strip() or "feiyang-lab"


def newapi_token_group() -> str:
    return os.environ.get("WEBUI_NEWAPI_TOKEN_GROUP", "image").strip()


def newapi_image_model() -> str:
    return os.environ.get("WEBUI_NEWAPI_IMAGE_MODEL", "gpt-image-2").strip() or "gpt-image-2"


def newapi_request_timeout_seconds() -> float:
    raw = os.environ.get("WEBUI_NEWAPI_REQUEST_TIMEOUT_SECONDS", "15").strip()
    try:
        value = float(raw)
    except (TypeError, ValueError):
        value = 15.0
    return max(1.0, value)
