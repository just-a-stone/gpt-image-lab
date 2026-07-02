from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request, Response

from codex_image.webui import feature_flags, newapi_broker
from codex_image.webui.context import WebUIContext
from codex_image.webui.security import check_request_origin
from codex_image.webui.owner import (
    clear_owner_cookie,
    compute_key_hash,
    resolve_owner,
    secret_is_persistent,
    set_owner_cookie,
)


def register_session_routes(app: FastAPI, ctx: WebUIContext) -> None:
    owner_store = ctx.owner_store

    @app.post("/api/session")
    async def create_session(request: Request, response: Response, payload: dict[str, Any] = Body(...)) -> dict[str, Any]:
        api_key = str(payload.get("api_key") or "").strip()
        if not api_key:
            raise HTTPException(status_code=400, detail="api_key is required")
        if owner_store is None:
            raise HTTPException(status_code=503, detail="owner store unavailable")
        key_hash = compute_key_hash(api_key)
        owner_id = owner_store.get_or_create(key_hash)
        set_owner_cookie(response, owner_id)
        return {"ok": True, "owner": owner_id[:6], "persistent_secret": secret_is_persistent()}

    @app.delete("/api/session")
    async def delete_session(response: Response) -> dict[str, Any]:
        clear_owner_cookie(response)
        return {"ok": True}

    @app.get("/api/session")
    async def session_status(request: Request) -> dict[str, Any]:
        owner_id = resolve_owner(request)
        if owner_id is None:
            return {"ok": False}
        return {"ok": True, "owner": owner_id[:6]}

    def _broker_newapi(request: Request) -> dict[str, Any] | None:
        if not feature_flags.newapi_enabled() or owner_store is None:
            return None
        session_cookie = request.cookies.get(feature_flags.newapi_cookie_name(), "")
        if not session_cookie:
            return None
        decoded = newapi_broker.decode_request_session(session_cookie)
        if not decoded:
            return None
        candidate_id = decoded.get("id")
        if not isinstance(candidate_id, int):
            return None
        user = newapi_broker.verify_user(session_cookie, candidate_id)
        if not user:
            return None
        username = str(user.get("username") or decoded.get("username") or "").strip()
        authoritative_id = user.get("id")
        if not isinstance(authoritative_id, int) or not username:
            return None
        token = newapi_broker.ensure_api_token(session_cookie, authoritative_id)
        if not token:
            return None
        owner_id = owner_store.get_or_create(compute_key_hash(username))
        return {"owner_id": owner_id, "username": username, "user_id": authoritative_id, "token": token}

    @app.get("/api/newapi/status")
    def newapi_status(request: Request) -> dict[str, Any]:
        if not feature_flags.newapi_enabled():
            return {"ok": False, "enabled": False}
        session_cookie = request.cookies.get(feature_flags.newapi_cookie_name(), "")
        decoded = newapi_broker.decode_request_session(session_cookie)
        if not decoded or not decoded.get("username"):
            return {"ok": False, "enabled": True}
        return {"ok": True, "enabled": True, "username": str(decoded["username"])}

    @app.post("/api/newapi/login")
    def newapi_login(request: Request, response: Response) -> dict[str, Any]:
        check_request_origin(request)
        if not feature_flags.newapi_enabled():
            raise HTTPException(status_code=503, detail="new-api integration is not configured")
        result = _broker_newapi(request)
        if result is None:
            raise HTTPException(status_code=401, detail="new-api session not found or invalid")
        set_owner_cookie(response, result["owner_id"])
        return {
            "ok": True,
            "username": result["username"],
            "owner": result["owner_id"][:6],
            "byok": {
                "api_key": result["token"],
                "base_url": feature_flags.newapi_base_url(),
                "image_model": feature_flags.newapi_image_model(),
            },
        }

    @app.delete("/api/newapi/logout")
    def newapi_logout(request: Request, response: Response) -> dict[str, Any]:
        check_request_origin(request)
        clear_owner_cookie(response)
        return {"ok": True}

