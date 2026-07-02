from __future__ import annotations

import base64
import binascii
import hmac
import hashlib
from typing import Any


class SecureCookieError(Exception):
    """Raised when a new-api session cookie cannot be decoded or verified."""


def _b64url_decode(value: str | bytes) -> bytes:
    raw = value.encode("utf-8") if isinstance(value, str) else value
    padding = b"=" * (-len(raw) % 4)
    try:
        return base64.urlsafe_b64decode(raw + padding)
    except (binascii.Error, ValueError) as exc:
        raise SecureCookieError("base64 decode failed") from exc


def _read_uvarint(buf: bytes, pos: int) -> tuple[int, int] | None:
    result = 0
    shift = 0
    while pos < len(buf):
        byte = buf[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7
        if shift > 63:
            return None
    return None


def _read_gob_string(buf: bytes, pos: int) -> str | None:
    pair = _read_uvarint(buf, pos)
    if pair is None:
        return None
    length, next_pos = pair
    if length < 0 or next_pos + length > len(buf):
        return None
    try:
        return buf[next_pos:next_pos + length].decode("utf-8")
    except UnicodeDecodeError:
        return None


def _read_gob_int(buf: bytes, pos: int) -> int | None:
    pair = _read_uvarint(buf, pos)
    if pair is None:
        return None
    value, _ = pair
    decoded = value >> 1
    if value & 1:
        decoded = ~decoded
    return decoded


def _iter_key_markers(gob: bytes, key: str):
    """Yield all positions where the gob string marker for *key* appears."""
    marker = bytes([len(key)]) + key.encode("utf-8")
    start = 0
    while True:
        idx = gob.find(marker, start)
        if idx < 0:
            return
        yield idx
        start = idx + 1


def _valid_string_field(key: str, value: str) -> bool:
    if not value or not value.isprintable():
        return False
    if key == "username":
        return len(value) <= 100
    if key == "group":
        return len(value) <= 50
    return False


def _valid_int_field(key: str, value: int) -> bool:
    if key == "id":
        return 1 <= value <= 100_000_000
    if key == "role":
        return 1 <= value <= 100
    if key == "status":
        return 1 <= value <= 10
    return False


def _extract_gob_fields(gob: bytes) -> dict[str, Any]:
    fields: dict[str, Any] = {}
    for key in ("username", "group"):
        for idx in _iter_key_markers(gob, key):
            value = _read_gob_string(gob, idx + len(key) + 1)
            if value is not None and _valid_string_field(key, value):
                fields[key] = value
                break
    for key in ("id", "role", "status"):
        for idx in _iter_key_markers(gob, key):
            value = _read_gob_int(gob, idx + len(key) + 1)
            if value is not None and _valid_int_field(key, value):
                fields[key] = value
                break
    return fields


def decode_session_cookie(cookie_value: str, secret: bytes, cookie_name: str = "session") -> dict[str, Any] | None:
    """Decode + HMAC-verify a gorilla/securecookie (gin-contrib) session cookie.

    Returns the session fields {id, username, role, status, group} on success,
    or None when the cookie is absent, malformed, or fails verification.
    """
    if not cookie_value or not secret or not cookie_name:
        return None
    try:
        raw = _b64url_decode(cookie_value)
    except SecureCookieError:
        return None
    parts = raw.split(b"|", 2)
    if len(parts) != 3:
        return None
    timestamp_b, payload_b, mac_b = parts
    mac_input = cookie_name.encode("utf-8") + b"|" + timestamp_b + b"|" + payload_b
    expected_mac = hmac.new(secret, mac_input, hashlib.sha256).digest()
    if not hmac.compare_digest(expected_mac, mac_b):
        return None
    try:
        gob = _b64url_decode(payload_b)
    except SecureCookieError:
        return None
    fields = _extract_gob_fields(gob)
    if "id" not in fields or "username" not in fields:
        return None
    return fields
