from __future__ import annotations

import base64
import binascii
import hashlib
import hmac
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


# ---------------------------------------------------------------------------
# gob decoder for gorilla/securecookie session values
#
# gorilla/securecookie (used by gin-contrib/sessions in new-api) serializes the
# session as a gob-encoded ``map[interface{}]interface{}`` whose keys are the
# strings passed to ``session.Set`` ("id", "username", "role", ...) and whose
# values are ``string`` or ``int``. Go's ``encoding/gob`` has its own wire
# format which must be followed exactly:
#
#   * Unsigned ints are NOT standard base-128 uvarint. A byte <= 0x7f is the
#     whole value; a byte > 0x7f means "read (256 - byte) more bytes, big-endian".
#   * The stream is a sequence of length-prefixed messages. Type-definition
#     messages come first (leading signed id < 0); the value message has a
#     leading signed id > 0.
#   * Interface values are encoded as
#     [nameLen][name][concreteTypeId][valueByteCount][fieldDelta 0][concreteValue]
#     where the concrete value is itself wrapped in a single-field struct.
#
# Earlier versions scraped the gob payload with byte markers + standard uvarint,
# which read gob type-name tokens ("string"/"int") instead of the real values,
# so every real new-api session cookie was rejected.
# ---------------------------------------------------------------------------


def _gob_uint(buf: bytes, pos: int) -> tuple[int, int]:
    """Decode a gob unsigned integer at *pos*; return (value, new_pos)."""
    first = buf[pos]
    pos += 1
    if first <= 0x7F:
        return first, pos
    count = 256 - first
    value = 0
    for _ in range(count):
        value = (value << 8) | buf[pos]
        pos += 1
    return value, pos


def _gob_int(buf: bytes, pos: int) -> tuple[int, int]:
    """Decode a gob signed (zigzag) integer at *pos*; return (value, new_pos)."""
    value, pos = _gob_uint(buf, pos)
    return (-((value >> 1)) - 1) if (value & 1) else (value >> 1), pos


def _decode_gob_interface(buf: bytes, pos: int) -> tuple[Any, int]:
    """Decode a gob interface value at *pos*; return (value, new_pos).

    Layout: ``[nameLen][name][concreteTypeId][valueByteCount][fieldDelta 0][value]``.
    """
    name_len, pos = _gob_uint(buf, pos)
    name = buf[pos:pos + name_len].decode("utf-8", "replace")
    pos += name_len
    if name_len == 0:
        return None, pos
    # Concrete type id (resolved by name below; consumed here).
    _concrete_id, pos = _gob_int(buf, pos)
    # Byte count of the delimited concrete value that follows.
    byte_count, pos = _gob_uint(buf, pos)
    value_start = pos
    # The concrete value is wrapped in a single-field struct (field delta 0).
    _field_delta, pos = _gob_uint(buf, pos)
    if name == "string":
        vlen, pos = _gob_uint(buf, pos)
        text = buf[pos:pos + vlen].decode("utf-8", "replace")
        return text, pos + vlen
    if name == "int":
        return _gob_int(buf, pos)
    if name == "bool":
        flag, pos = _gob_uint(buf, pos)
        return flag != 0, pos
    # Unknown concrete type: skip the rest of the delimited value.
    return None, value_start + byte_count


def _decode_gob_session_map(data: bytes) -> dict[Any, Any] | None:
    """Decode a gob stream holding a ``map[interface{}]interface{}``.

    Returns the decoded mapping, or ``None`` if no value message is present.
    Raises ``IndexError``/``ValueError`` on malformed input so that callers can
    treat the session as invalid.
    """
    pos = 0
    total = len(data)
    while pos < total:
        msg_len, pos = _gob_uint(data, pos)
        body = data[pos:pos + msg_len]
        pos += msg_len
        if not body:
            continue
        type_id, body_pos = _gob_int(body, 0)
        if type_id < 0:
            # Type-definition message; its details are not needed because the
            # top-level value is always the gorilla session map.
            continue
        # Value message: [field delta 0][entry count][key/value interface pairs].
        _field_delta, body_pos = _gob_uint(body, body_pos)
        entry_count, body_pos = _gob_uint(body, body_pos)
        result: dict[Any, Any] = {}
        for _ in range(entry_count):
            key, body_pos = _decode_gob_interface(body, body_pos)
            value, body_pos = _decode_gob_interface(body, body_pos)
            result[key] = value
        return result
    return None


def decode_session_cookie(cookie_value: str, secret: bytes, cookie_name: str = "session") -> dict[str, Any] | None:
    """Decode + HMAC-verify a gorilla/securecookie (gin-contrib) session cookie.

    Returns the session fields {id, username, role, status, group, ...} on
    success, or None when the cookie is absent, malformed, fails verification,
    or does not carry the identity fields required by the broker.
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
        fields = _decode_gob_session_map(gob)
    except (SecureCookieError, IndexError, ValueError):
        return None
    if not fields:
        return None
    if not isinstance(fields.get("id"), int) or not isinstance(fields.get("username"), str):
        return None
    return fields
