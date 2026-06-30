from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse

from codex_image.webui.context import WebUIContext
from codex_image.webui.owner import resolve_owner
from codex_image.webui.storage import _guess_mime_type

_TASK_ID_RE = re.compile(r"(\d{8}\d{6}-[0-9a-fA-F]{8})")


def _extract_task_id(filename: str) -> str | None:
    match = _TASK_ID_RE.search(filename)
    return match.group(1) if match else None


def _resolve_within_root(root: Path, rest: str) -> Path:
    root_resolved = root.resolve(strict=False)
    candidate = (root / rest).resolve(strict=False)
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    return candidate


def _assert_task_owner(ctx: WebUIContext, task_id: str, owner: str) -> None:
    try:
        metadata = ctx.storage.read_metadata(task_id)
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Not found") from exc
    if str(metadata.get("owner") or "") != owner:
        raise HTTPException(status_code=404, detail="Not found")


def register_asset_routes(app: FastAPI, ctx: WebUIContext) -> None:
    @app.get("/api/outputs/{rest:path}")
    def serve_output(rest: str, request: Request) -> Any:
        owner = resolve_owner(request) or ""
        path = _resolve_within_root(ctx.output_root, rest)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        task_id = _extract_task_id(path.name)
        if not task_id:
            raise HTTPException(status_code=404, detail="Not found")
        _assert_task_owner(ctx, task_id, owner)
        return FileResponse(path, headers={"Cache-Control": "private, max-age=31536000, immutable"})

    @app.get("/api/inputs/{rest:path}")
    def serve_input(rest: str, request: Request) -> Any:
        owner = resolve_owner(request) or ""
        path = _resolve_within_root(ctx.input_root, rest)
        if not path.is_file():
            raise HTTPException(status_code=404, detail="Not found")
        task_id = _extract_task_id(path.name)
        if not task_id:
            raise HTTPException(status_code=404, detail="Not found")
        _assert_task_owner(ctx, task_id, owner)
        return FileResponse(path, headers={"Cache-Control": "private, max-age=31536000, immutable"})
