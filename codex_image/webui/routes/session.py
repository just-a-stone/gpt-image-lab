from __future__ import annotations

from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request, Response

from codex_image.webui.context import WebUIContext
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
