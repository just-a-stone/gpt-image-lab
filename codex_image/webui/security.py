from __future__ import annotations

from urllib.parse import urlparse

from fastapi import HTTPException, Request


def check_request_origin(request: Request) -> None:
    """Reject cross-origin requests to state-changing endpoints.

    Browsers always send an ``Origin`` header on cross-origin POST/DELETE.
    If the header is absent the request is treated as same-origin (or a
    direct API call) and allowed through. When present, the origin's netloc
    must match the request ``Host`` header.
    """
    host = request.headers.get("host", "")
    if not host:
        return
    for header in ("origin", "referer"):
        value = request.headers.get(header, "")
        if not value:
            continue
        netloc = urlparse(value).netloc
        if netloc and netloc != host:
            raise HTTPException(status_code=403, detail="cross-origin request blocked")
