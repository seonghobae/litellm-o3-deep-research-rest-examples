from __future__ import annotations

import io
import json

import pytest

from litellm_example.client import (
    LiteLLMClient,
    LiteLLMError,
    _normalize_base_url,
)


class FakeResponse:
    def __init__(self, body: bytes, status: int = 200) -> None:
        self.status = status
        self._body = body

    def read(self) -> bytes:
        return self._body

    def getcode(self) -> int:
        return self.status

    def __enter__(self) -> "FakeResponse":
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        return False


def test_normalize_base_url_accepts_root_and_v1() -> None:
    assert _normalize_base_url("https://example.com") == "https://example.com/v1/"
    assert _normalize_base_url("https://example.com/") == "https://example.com/v1/"
    assert _normalize_base_url("https://example.com/v1") == "https://example.com/v1/"
    assert _normalize_base_url("https://example.com/v1/") == "https://example.com/v1/"


@pytest.mark.parametrize(
    "value",
    [
        "http://example.com",  # cleartext remote host not allowed
        "http://example.com/api",
        "http://example.com/v2",
        "example.com",
    ],
)
def test_normalize_base_url_rejects_unexpected_paths(value: str) -> None:
    with pytest.raises((ValueError,)):  # path or scheme issues
        _normalize_base_url(value)


def test_client_builds_expected_request(monkeypatch: pytest.MonkeyPatch) -> None:
    captured = {}

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        captured["url"] = req.full_url
        captured["headers"] = {key.lower(): value for key, value in req.header_items()}
        body = json.dumps(
            {
                "choices": [
                    {
                        "message": {"role": "assistant", "content": "hello from o3"},
                    }
                ]
            }
        ).encode("utf-8")
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_chat_completion("Hi")

    assert text == "hello from o3"
    assert captured["url"] == "https://example.com/v1/chat/completions"
    assert captured["headers"]["authorization"].startswith("Bearer ")
    assert "application/json" in captured["headers"]["content-type"]


def test_responses_api_uses_expected_url_and_body(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        captured["url"] = req.full_url
        captured["headers"] = {key.lower(): value for key, value in req.header_items()}
        captured["body"] = json.loads(req.data.decode("utf-8"))  # type: ignore[attr-defined]
        body = json.dumps(
            {
                "output": [
                    {
                        "content": [
                            {
                                "type": "output_text",
                                "text": {"value": "ok from responses"},
                            }
                        ]
                    }
                ]
            }
        ).encode("utf-8")
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")

    text = c.create_response("Hi via responses")  # type: ignore[attr-defined]

    assert text == "ok from responses"
    assert captured["url"] == "https://example.com/v1/responses"
    assert captured["headers"]["authorization"].startswith("Bearer ")  # type: ignore[index]
    assert captured["body"] == {  # type: ignore[index]
        "model": "o3-deep-research",
        "input": "Hi via responses",
    }


def test_background_responses_includes_flag_and_returns_raw_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        captured["body"] = json.loads(req.data.decode("utf-8"))  # type: ignore[attr-defined]
        body = json.dumps(
            {
                "id": "resp_background_123",
                "object": "response",
                "status": "queued",
                "background": True,
            }
        ).encode("utf-8")
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_response("Queue this in background", background=True)  # type: ignore[call-arg]

    assert captured["body"] == {  # type: ignore[index]
        "model": "o3-deep-research",
        "input": "Queue this in background",
        "background": True,
    }
    assert json.loads(text) == {
        "id": "resp_background_123",
        "object": "response",
        "status": "queued",
        "background": True,
    }


def test_client_raises_on_error_response(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {"error": {"message": "bad request", "type": "invalid_request_error"}}
        ).encode("utf-8")
        # Simulate HTTPError path by raising here
        raise client_module.error.HTTPError(
            url=req.full_url,
            code=400,
            msg="Bad Request",
            hdrs=None,
            fp=io.BytesIO(body),
        )

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("Hi")

    err = excinfo.value
    assert err.status == 400
    assert "bad request" in str(err).lower()
