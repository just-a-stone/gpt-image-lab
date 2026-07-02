from __future__ import annotations

import base64
import hashlib
import hmac
import unittest

from codex_image.webui.newapi_securecookie import (
    _extract_gob_fields,
    _read_gob_int,
    _read_gob_string,
    decode_session_cookie,
)


def _uvarint(value: int) -> bytes:
    out = bytearray()
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return bytes(out)


def _gob_string(value: str) -> bytes:
    raw = value.encode("utf-8")
    return _uvarint(len(raw)) + raw


def _gob_int(value: int) -> bytes:
    if value < 0:
        encoded = ((-value) << 1) | 1
    else:
        encoded = value << 1
    return _uvarint(encoded)


def _build_session_gob(fields: dict[str, object]) -> bytes:
    blob = bytearray()
    for key, value in fields.items():
        blob += _gob_string(key)
        if isinstance(value, str):
            blob += _gob_string(value)
        else:
            blob += _gob_int(int(value))
    return bytes(blob)


def _make_cookie(name: str, timestamp: int, payload: bytes, secret: bytes) -> str:
    payload_b64 = base64.urlsafe_b64encode(payload).rstrip(b"=")
    mac_input = name.encode("utf-8") + b"|" + str(timestamp).encode("ascii") + b"|" + payload_b64
    mac = hmac.new(secret, mac_input, hashlib.sha256).digest()
    raw = str(timestamp).encode("ascii") + b"|" + payload_b64 + b"|" + mac
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


SECRET = b"test-session-secret-please-not-in-prod"
NAME = "session"


class GobExtractionTests(unittest.TestCase):
    def test_read_string_and_int_roundtrip(self) -> None:
        self.assertEqual(_read_gob_string(_gob_string("alice"), 0), "alice")
        self.assertEqual(_read_gob_int(_gob_int(5), 0), 5)
        self.assertEqual(_read_gob_int(_gob_int(0), 0), 0)
        self.assertEqual(_read_gob_int(_gob_int(12345), 0), 12345)

    def test_extract_known_fields(self) -> None:
        gob = _build_session_gob({"id": 5, "username": "alice", "role": 1, "status": 1, "group": "image"})
        fields = _extract_gob_fields(gob)
        self.assertEqual(fields.get("id"), 5)
        self.assertEqual(fields.get("username"), "alice")
        self.assertEqual(fields.get("role"), 1)
        self.assertEqual(fields.get("status"), 1)
        self.assertEqual(fields.get("group"), "image")

    def test_extract_missing_keys_returns_partial(self) -> None:
        gob = _build_session_gob({"id": 7, "username": "bob"})
        fields = _extract_gob_fields(gob)
        self.assertEqual(fields.get("id"), 7)
        self.assertEqual(fields.get("username"), "bob")
        self.assertNotIn("group", fields)


class DecodeSessionCookieTests(unittest.TestCase):
    def _cookie(self, fields: dict[str, object], secret: bytes = SECRET, name: str = NAME, timestamp: int = 1_700_000_000) -> str:
        return _make_cookie(name, timestamp, _build_session_gob(fields), secret)

    def test_valid_cookie_decodes_fields(self) -> None:
        cookie = self._cookie({"id": 42, "username": "carol", "group": "image"})
        decoded = decode_session_cookie(cookie, SECRET, NAME)
        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertEqual(decoded["id"], 42)
        self.assertEqual(decoded["username"], "carol")
        self.assertEqual(decoded["group"], "image")

    def test_rejects_wrong_secret(self) -> None:
        cookie = self._cookie({"id": 1, "username": "x"})
        self.assertIsNone(decode_session_cookie(cookie, b"different-secret", NAME))

    def test_rejects_tampered_payload(self) -> None:
        cookie = self._cookie({"id": 1, "username": "x"})
        self.assertIsNone(decode_session_cookie(cookie + "AA", SECRET, NAME))

    def test_rejects_empty_and_garbage(self) -> None:
        self.assertIsNone(decode_session_cookie("", SECRET, NAME))
        self.assertIsNone(decode_session_cookie("not-a-real-cookie", SECRET, NAME))
        self.assertIsNone(decode_session_cookie("!!!badbase64!!!", SECRET, NAME))

    def test_rejects_missing_identity_fields(self) -> None:
        cookie = _make_cookie(NAME, 1_700_000_000, _gob_string("group") + _gob_string("image"), SECRET)
        self.assertIsNone(decode_session_cookie(cookie, SECRET, NAME))


if __name__ == "__main__":
    unittest.main()
