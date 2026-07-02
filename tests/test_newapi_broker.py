from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch

from codex_image.webui import feature_flags, newapi_broker


class _FakeResponse(io.BytesIO):
    def __enter__(self) -> "_FakeResponse":
        return self

    def __exit__(self, *args: object) -> None:
        self.close()


def _resp(payload: dict[str, object]) -> _FakeResponse:
    return _FakeResponse(json.dumps(payload).encode("utf-8"))


class BrokerHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        self.base = "https://api.feiyang.click"
        self.session = "encrypted-session-cookie-value"
        patcher_flags = patch.multiple(
            feature_flags,
            newapi_base_url=lambda: self.base,
            newapi_enabled=lambda: True,
            newapi_session_secret=lambda: b"secret",
            newapi_cookie_name=lambda: "session",
            newapi_token_name=lambda: "feiyang-lab",
            newapi_token_group=lambda: "image",
            newapi_image_model=lambda: "gpt-image-2",
            newapi_request_timeout_seconds=lambda: 5.0,
        )
        patcher_flags.start()
        self.addCleanup(patcher_flags.stop)

    def test_verify_user_success(self) -> None:
        payload = {"success": True, "data": {"id": 5, "username": "alice", "role": 1, "status": 1}}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen", return_value=_resp(payload)):
            user = newapi_broker.verify_user(self.session, 5)
        self.assertEqual(user, {"id": 5, "username": "alice", "role": 1, "status": 1})

    def test_verify_user_failure(self) -> None:
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen", return_value=_resp({"success": False})):
            self.assertIsNone(newapi_broker.verify_user(self.session, 5))
        import urllib.error
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen", side_effect=urllib.error.URLError("boom")):
            self.assertIsNone(newapi_broker.verify_user(self.session, 5))

    def test_ensure_api_token_finds_existing(self) -> None:
        existing = {"success": True, "data": {"items": [
            {"id": 10, "name": "feiyang-lab", "group": "image"},
            {"id": 11, "name": "other", "group": "default"},
        ], "total": 2}}
        key = {"success": True, "data": "sk-found-token"}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen", side_effect=[_resp(existing), _resp(key)]):
            token = newapi_broker.ensure_api_token(self.session, 5)
        self.assertEqual(token, "sk-found-token")

    def test_ensure_api_token_creates_when_missing(self) -> None:
        empty = {"success": True, "data": {"items": [], "total": 0}}
        created = {"success": True, "data": {"items": [{"id": 99, "name": "feiyang-lab", "group": "image"}], "total": 1}}
        create_ok = {"success": True}
        key = {"success": True, "data": "sk-created-token"}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen", side_effect=[_resp(empty), _resp(create_ok), _resp(created), _resp(key)]):
            token = newapi_broker.ensure_api_token(self.session, 5)
        self.assertEqual(token, "sk-created-token")

    def test_ensure_api_token_ignores_wrong_group(self) -> None:
        wrong_group = {"success": True, "data": {"items": [
            {"id": 10, "name": "feiyang-lab", "group": "default"},
        ], "total": 1}}
        created = {"success": True, "data": {"items": [{"id": 12, "name": "feiyang-lab", "group": "image"}], "total": 1}}
        create_ok = {"success": True}
        key = {"success": True, "data": "sk-right-group"}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen", side_effect=[_resp(wrong_group), _resp(create_ok), _resp(created), _resp(key)]):
            token = newapi_broker.ensure_api_token(self.session, 5)
        self.assertEqual(token, "sk-right-group")

    def test_ensure_api_token_returns_none_when_key_fetch_fails(self) -> None:
        existing = {"success": True, "data": {"items": [{"id": 10, "name": "feiyang-lab", "group": "image"}], "total": 1}}
        key_fail = {"success": False}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen", side_effect=[_resp(existing), _resp(key_fail)]):
            self.assertIsNone(newapi_broker.ensure_api_token(self.session, 5))

    def test_ensure_api_token_reenables_disabled(self) -> None:
        disabled = {"success": True, "data": {"items": [
            {"id": 10, "name": "feiyang-lab", "group": "image", "status": 2},
        ], "total": 1}}
        reenable_ok = {"success": True}
        key = {"success": True, "data": "sk-token"}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen",
                   side_effect=[_resp(disabled), _resp(reenable_ok), _resp(key)]):
            token = newapi_broker.ensure_api_token(self.session, 5)
        self.assertEqual(token, "sk-token")

    def test_disable_user_token_disables_enabled(self) -> None:
        enabled = {"success": True, "data": {"items": [
            {"id": 10, "name": "feiyang-lab", "group": "image", "status": 1},
        ], "total": 1}}
        disable_ok = {"success": True}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen",
                   side_effect=[_resp(enabled), _resp(disable_ok)]):
            newapi_broker.disable_user_token(self.session, 5)

    def test_disable_user_token_noop_when_already_disabled(self) -> None:
        disabled = {"success": True, "data": {"items": [
            {"id": 10, "name": "feiyang-lab", "group": "image", "status": 2},
        ], "total": 1}}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen",
                   side_effect=[_resp(disabled)]):
            newapi_broker.disable_user_token(self.session, 5)

    def test_disable_user_token_noop_when_not_found(self) -> None:
        other = {"success": True, "data": {"items": [
            {"id": 10, "name": "other", "group": "default", "status": 1},
        ], "total": 1}}
        with patch("codex_image.webui.newapi_broker.urllib.request.urlopen",
                   side_effect=[_resp(other)]):
            newapi_broker.disable_user_token(self.session, 5)


class DecodeRequestSessionTests(unittest.TestCase):
    def test_returns_none_when_disabled(self) -> None:
        with patch.object(feature_flags, "newapi_session_secret", lambda: b""):
            self.assertIsNone(newapi_broker.decode_request_session("anything"))


if __name__ == "__main__":
    unittest.main()
