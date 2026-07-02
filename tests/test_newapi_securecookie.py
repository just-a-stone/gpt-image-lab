from __future__ import annotations

import base64
import hashlib
import hmac
import unittest

from codex_image.webui.newapi_securecookie import (
    _decode_gob_session_map,
    _gob_int,
    _gob_uint,
    decode_session_cookie,
)


# Real gob blobs produced by Go's encoding/gob for a map[interface{}]interface{}
# with the exact layout gorilla/securecookie (gin-contrib/sessions) emits.
# (Regenerate with: gob.NewEncoder(buf).Encode(map[interface{}]interface{}{...}))
GOB_FULL = bytes.fromhex(
    "0d7f040102ff8000011001100000ff90ff80000506737472696e670c0800067374617475730369"
    "6e740402000206737472696e670c07000567726f757006737472696e670c09000764656661756c"
    "7406737472696e670c040002696403696e740402000206737472696e670c0a0008757365726e61"
    "6d6506737472696e670c080006736869656c6406737472696e670c060004726f6c6503696e7404"
    "0300ffc8"
)
GOB_IDONLY = bytes.fromhex(
    "0d7f040102ff80000110011000005cff80000306737472696e670c07000567726f757006737472"
    "696e670c070005696d61676506737472696e670c040002696403696e740402005406737472696e"
    "670c0a0008757365726e616d6506737472696e670c0700056361726f6c"
)
GOB_GROUP_ONLY = bytes.fromhex(
    "0d7f040102ff800001100110000024ff80000106737472696e670c07000567726f757006737472"
    "696e670c070005696d616765"
)
GOB_MINIMAL = bytes.fromhex(
    "0d7f040102ff800001100110000038ff80000206737472696e670c0a0008757365726e616d6506"
    "737472696e670c0300017806737472696e670c040002696403696e7404020002"
)
GOB_LONG_AND_UNICODE = bytes.fromhex(
    "0d7f040102ff8000011001100000ff9fff80000506737472696e670c07000567726f7570067374"
    "72696e670c0300017806737472696e670c040002696403696e74040500fd1e847e06737472696e"
    "670c0a0008757365726e616d6506737472696e670c1b0019612d766572792d6c6f6e672d757365"
    "726e616d652d6865726506737472696e670c060004726f6c6503696e740402001406737472696e"
    "670c08000673746174757303696e7404020002"
)


SECRET = b"test-session-secret-please-not-in-prod"
NAME = "session"


def _make_cookie(name: str, timestamp: int, gob_payload: bytes, secret: bytes) -> str:
    payload_b64 = base64.urlsafe_b64encode(gob_payload).rstrip(b"=")
    mac_input = name.encode("utf-8") + b"|" + str(timestamp).encode("ascii") + b"|" + payload_b64
    mac = hmac.new(secret, mac_input, hashlib.sha256).digest()
    raw = str(timestamp).encode("ascii") + b"|" + payload_b64 + b"|" + mac
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


class GobUintTests(unittest.TestCase):
    def test_single_byte_values(self) -> None:
        # Bytes <= 0x7f encode themselves directly.
        for b in (0, 1, 0x7F):
            self.assertEqual(_gob_uint(bytes([b]), 0), (b, 1))

    def test_multi_byte_big_endian(self) -> None:
        # 0xff -> read 1 more byte (big-endian); 0xfe -> 2 more bytes; etc.
        self.assertEqual(_gob_uint(bytes([0xFF, 0x90]), 0), (0x90, 2))
        self.assertEqual(_gob_uint(bytes([0xFE, 0x01, 0x00]), 0), (0x0100, 3))

    def test_signed_zigzag_roundtrip(self) -> None:
        def encode_uint(n: int) -> bytes:
            if n <= 0x7F:
                return bytes([n])
            buf = []
            v = n
            while v:
                buf.append(v & 0xFF)
                v >>= 8
            return bytes([256 - len(buf)]) + bytes(reversed(buf))

        for value in (0, 1, -1, 5, 100, -100, 999999):
            # gob's signed encoding: x>>1, with x&1 inverting the bits (i = ^(x>>1)).
            zigzag = (value << 1) if value >= 0 else (((-value - 1) << 1) | 1)
            self.assertEqual(_gob_int(encode_uint(zigzag), 0)[0], value)


class GobSessionMapTests(unittest.TestCase):
    def test_decode_full_session(self) -> None:
        self.assertEqual(
            _decode_gob_session_map(GOB_FULL),
            {"status": 1, "group": "default", "id": 1, "username": "shield", "role": 100},
        )

    def test_decode_partial_session(self) -> None:
        self.assertEqual(
            _decode_gob_session_map(GOB_IDONLY),
            {"group": "image", "id": 42, "username": "carol"},
        )

    def test_decode_long_and_unicode_username(self) -> None:
        self.assertEqual(
            _decode_gob_session_map(GOB_LONG_AND_UNICODE),
            {"group": "x", "id": 999999, "username": "a-very-long-username-here", "role": 10, "status": 1},
        )

    def test_decode_minimal_session(self) -> None:
        self.assertEqual(_decode_gob_session_map(GOB_MINIMAL), {"id": 1, "username": "x"})

    def test_malformed_returns_none_or_raises(self) -> None:
        # Truncated payload raises IndexError (decode_session_cookie swallows it).
        with self.assertRaises(Exception):
            _decode_gob_session_map(b"\xff")


class DecodeSessionCookieTests(unittest.TestCase):
    def test_valid_cookie_decodes_fields(self) -> None:
        cookie = _make_cookie(NAME, 1_700_000_000, GOB_IDONLY, SECRET)
        decoded = decode_session_cookie(cookie, SECRET, NAME)
        self.assertIsNotNone(decoded)
        assert decoded is not None
        self.assertEqual(decoded["id"], 42)
        self.assertEqual(decoded["username"], "carol")
        self.assertEqual(decoded["group"], "image")
        self.assertIsInstance(decoded["id"], int)

    def test_valid_cookie_full_session(self) -> None:
        cookie = _make_cookie(NAME, 1_783_004_558, GOB_FULL, SECRET)
        decoded = decode_session_cookie(cookie, SECRET, NAME)
        assert decoded is not None
        self.assertEqual(decoded["username"], "shield")
        self.assertEqual(decoded["role"], 100)

    def test_rejects_wrong_secret(self) -> None:
        cookie = _make_cookie(NAME, 1_700_000_000, GOB_MINIMAL, SECRET)
        self.assertIsNone(decode_session_cookie(cookie, b"different-secret", NAME))

    def test_rejects_tampered_payload(self) -> None:
        cookie = _make_cookie(NAME, 1_700_000_000, GOB_MINIMAL, SECRET)
        self.assertIsNone(decode_session_cookie(cookie + "AA", SECRET, NAME))

    def test_rejects_empty_and_garbage(self) -> None:
        self.assertIsNone(decode_session_cookie("", SECRET, NAME))
        self.assertIsNone(decode_session_cookie("not-a-real-cookie", SECRET, NAME))
        self.assertIsNone(decode_session_cookie("!!!badbase64!!!", SECRET, NAME))

    def test_rejects_missing_identity_fields(self) -> None:
        # A session with only "group" (no id/username) is not a usable identity.
        cookie = _make_cookie(NAME, 1_700_000_000, GOB_GROUP_ONLY, SECRET)
        self.assertIsNone(decode_session_cookie(cookie, SECRET, NAME))


if __name__ == "__main__":
    unittest.main()
