from __future__ import annotations

import unittest

from fastapi import HTTPException

from codex_image.webui.security import check_request_origin


class _FakeRequest:
    def __init__(self, headers: dict[str, str]) -> None:
        self.headers = headers


class CheckOriginTests(unittest.TestCase):
    def test_same_origin_passes(self) -> None:
        req = _FakeRequest({"host": "img.example.com", "origin": "https://img.example.com"})
        check_request_origin(req)

    def test_cross_origin_blocked(self) -> None:
        req = _FakeRequest({"host": "img.example.com", "origin": "https://evil.com"})
        with self.assertRaises(HTTPException) as ctx:
            check_request_origin(req)
        self.assertEqual(ctx.exception.status_code, 403)

    def test_no_origin_passes(self) -> None:
        req = _FakeRequest({"host": "img.example.com"})
        check_request_origin(req)

    def test_no_host_passes(self) -> None:
        req = _FakeRequest({"origin": "https://evil.com"})
        check_request_origin(req)

    def test_referer_same_origin_passes(self) -> None:
        req = _FakeRequest({"host": "img.example.com", "referer": "https://img.example.com/api/generate"})
        check_request_origin(req)

    def test_referer_cross_origin_blocked(self) -> None:
        req = _FakeRequest({"host": "img.example.com", "referer": "https://evil.com/page"})
        with self.assertRaises(HTTPException):
            check_request_origin(req)

    def test_origin_takes_precedence_over_referer(self) -> None:
        req = _FakeRequest({
            "host": "img.example.com",
            "origin": "https://evil.com",
            "referer": "https://img.example.com/page",
        })
        with self.assertRaises(HTTPException):
            check_request_origin(req)


if __name__ == "__main__":
    unittest.main()
