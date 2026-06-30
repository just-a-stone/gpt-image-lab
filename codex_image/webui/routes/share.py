from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse

from codex_image.webui.context import WebUIContext
from codex_image.webui.owner import resolve_owner
from codex_image.webui.share_store import ShareStore, SHARE_STATUS_ACTIVE
from codex_image.webui.storage_utils import _guess_mime_type

SAFE_PARAM_KEYS = {"size", "quality", "background", "n", "main_model"}


def _build_safe_params(metadata: dict[str, Any]) -> dict[str, Any]:
    params = metadata.get("params")
    if not isinstance(params, dict):
        return {}
    return {k: v for k, v in params.items() if k in SAFE_PARAM_KEYS}


def _get_output_files(metadata: dict[str, Any]) -> list[str]:
    files = metadata.get("output_files")
    if isinstance(files, list) and files:
        return [str(f) for f in files if f]
    single = metadata.get("output_file")
    return [str(single)] if single else []


def _build_shared_response(
    share_row: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    share_id = str(share_row["share_id"])
    show_prompt = bool(share_row["show_prompt"])
    output_files = _get_output_files(metadata)
    output_urls = [f"/api/shared/{share_id}/assets/{i}" for i in range(len(output_files))]
    thumb_urls = [f"/api/shared/{share_id}/assets/{i}?size=thumb" for i in range(len(output_files))]
    return {
        "share_id": share_id,
        "prompt": str(metadata.get("prompt") or "") if show_prompt else "",
        "show_prompt": show_prompt,
        "safe_params": _build_safe_params(metadata),
        "output_urls": output_urls,
        "thumb_urls": thumb_urls,
        "shared_at": str(share_row["shared_at"]),
        "shared_by": str(share_row["public_author_id"]),
        "share_note": str(share_row.get("share_note") or ""),
    }


def register_share_routes(app: FastAPI, ctx: WebUIContext) -> None:
    share_store = ShareStore(ctx.storage.task_index.path)

    def _resolve_share_store() -> ShareStore:
        return share_store

    @app.post("/api/tasks/{task_id}/share")
    def create_share(task_id: str, request: Request, payload: dict[str, Any] | None = None) -> dict[str, Any]:
        owner = resolve_owner(request) or ""
        try:
            metadata = ctx.storage.read_metadata(task_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        if str(metadata.get("owner") or "") != owner:
            raise HTTPException(status_code=404, detail="Task not found")
        if not _get_output_files(metadata):
            raise HTTPException(status_code=409, detail="Task has no output files to share")
        body = payload or {}
        show_prompt = bool(body.get("show_prompt", True))
        share_note = str(body.get("share_note") or "")[:500]
        result = share_store.create_share(
            task_id=task_id,
            owner=owner,
            show_prompt=show_prompt,
            share_note=share_note,
        )
        return {"share": result}

    @app.patch("/api/tasks/{task_id}/share")
    def update_share(task_id: str, request: Request, payload: dict[str, Any] = ...) -> dict[str, Any]:
        owner = resolve_owner(request) or ""
        try:
            metadata = ctx.storage.read_metadata(task_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        if str(metadata.get("owner") or "") != owner:
            raise HTTPException(status_code=404, detail="Task not found")
        show_prompt = bool(payload.get("show_prompt")) if "show_prompt" in payload else None
        share_note = str(payload.get("share_note") or "")[:500] if "share_note" in payload else None
        updated = share_store.update_share(
            task_id=task_id,
            owner=owner,
            show_prompt=show_prompt,
            share_note=share_note,
        )
        if updated is None:
            raise HTTPException(status_code=404, detail="Share not found or not active")
        return {"share": {
            "share_id": str(updated["share_id"]),
            "task_id": str(updated["task_id"]),
            "shared_at": str(updated["shared_at"]),
            "show_prompt": bool(updated["show_prompt"]),
            "share_note": str(updated.get("share_note") or ""),
            "status": str(updated["status"]),
        }}

    @app.delete("/api/tasks/{task_id}/share")
    def revoke_share(task_id: str, request: Request) -> dict[str, Any]:
        owner = resolve_owner(request) or ""
        try:
            metadata = ctx.storage.read_metadata(task_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        if str(metadata.get("owner") or "") != owner:
            raise HTTPException(status_code=404, detail="Task not found")
        share_store.revoke_share(task_id=task_id, owner=owner)
        return {"shared": False}

    @app.get("/api/tasks/{task_id}/share")
    def get_share_status(task_id: str, request: Request) -> dict[str, Any]:
        owner = resolve_owner(request) or ""
        try:
            metadata = ctx.storage.read_metadata(task_id)
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Task not found") from exc
        if str(metadata.get("owner") or "") != owner:
            raise HTTPException(status_code=404, detail="Task not found")
        share = share_store.get_share_by_task(task_id)
        if share and share["status"] == SHARE_STATUS_ACTIVE:
            return {
                "shared": True,
                "share_id": str(share["share_id"]),
                "shared_at": str(share["shared_at"]),
                "show_prompt": bool(share["show_prompt"]),
                "share_note": str(share.get("share_note") or ""),
            }
        return {"shared": False}

    @app.get("/api/shared")
    def list_shared(
        cursor: str | None = Query(None),
        limit: int = Query(24, ge=1, le=60),
    ) -> dict[str, Any]:
        page = share_store.list_active_shares(limit=limit, cursor=cursor)
        items: list[dict[str, Any]] = []
        for share_row in page["items"]:
            try:
                metadata = ctx.storage.read_metadata(str(share_row["task_id"]))
            except (FileNotFoundError, ValueError):
                continue
            if not _get_output_files(metadata):
                continue
            items.append(_build_shared_response(share_row, metadata))
        return {
            "items": items,
            "next_cursor": page["next_cursor"],
        }

    @app.get("/api/shared/{share_id}")
    def get_shared_item(share_id: str) -> dict[str, Any]:
        share_row = share_store.get_active_share(share_id)
        if share_row is None:
            raise HTTPException(status_code=404, detail="Not found")
        try:
            metadata = ctx.storage.read_metadata(str(share_row["task_id"]))
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc
        return _build_shared_response(share_row, metadata)

    @app.get("/api/shared/{share_id}/assets/{idx}")
    def serve_shared_asset(
        share_id: str,
        idx: str,
        size: str | None = Query(None),
    ) -> Any:
        share_row = share_store.get_active_share(share_id)
        if share_row is None:
            raise HTTPException(status_code=404, detail="Not found")
        try:
            metadata = ctx.storage.read_metadata(str(share_row["task_id"]))
        except (FileNotFoundError, ValueError) as exc:
            raise HTTPException(status_code=404, detail="Not found") from exc

        output_files = _get_output_files(metadata)
        try:
            asset_index = int(idx)
        except ValueError:
            raise HTTPException(status_code=404, detail="Not found")
        if asset_index < 0 or asset_index >= len(output_files):
            raise HTTPException(status_code=404, detail="Not found")

        if size == "thumb":
            task_id = str(share_row["task_id"])
            thumb_path = ctx.storage.output_thumbnail_path(task_id, asset_index + 1)
            if thumb_path.is_file():
                return FileResponse(
                    thumb_path,
                    headers={"Cache-Control": "public, max-age=300"},
                    media_type=_guess_mime_type(str(thumb_path)),
                )

        filename = output_files[asset_index]
        file_path = ctx.storage.output_path(filename)
        if not file_path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        return FileResponse(
            file_path,
            headers={"Cache-Control": "public, max-age=300"},
            media_type=_guess_mime_type(str(file_path)),
        )
