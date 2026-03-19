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


# --------------------------------------------------------------------------- #
# _extract_response_content: top-level output_text path (H-5)                #
# --------------------------------------------------------------------------- #


def test_responses_api_returns_top_level_output_text_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the isinstance(output_text, str) early-return in _extract_response_content."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps({"output_text": "top-level text value"}).encode("utf-8")
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_response("Top-level output question")  # type: ignore[attr-defined]

    assert text == "top-level text value"


def test_responses_api_raises_on_empty_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """_extract_response_content raises LiteLLMError when no output items exist."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps({"output": []}).encode("utf-8")
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_response("No output question")  # type: ignore[attr-defined]

    assert excinfo.value.status == 200


# --------------------------------------------------------------------------- #
# _extract_content: list-of-blocks branch (H-6) and 200-no-content (H-7)     #
# --------------------------------------------------------------------------- #


def test_chat_completion_handles_list_of_content_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the isinstance(content, list) branch in _extract_content."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {
                "choices": [
                    {
                        "message": {
                            "role": "assistant",
                            "content": [
                                {"type": "text", "text": "block-"},
                                {"type": "text", "text": "answer"},
                            ],
                        }
                    }
                ]
            }
        ).encode("utf-8")
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_chat_completion("Blocks question")

    assert text == "block-answer"


def test_chat_completion_raises_when_content_is_empty_string(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover the LiteLLMError raise in _extract_content when content is empty."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {"choices": [{"message": {"role": "assistant", "content": ""}}]}
        ).encode("utf-8")
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("Empty content question")

    assert excinfo.value.status == 200
    assert "usable" in str(excinfo.value).lower()


# --------------------------------------------------------------------------- #
# _normalize_base_url: scheme and security guard paths                        #
# --------------------------------------------------------------------------- #


def test_normalize_base_url_rejects_non_http_scheme() -> None:
    """Cover line 44: scheme not in {https, http} raises ValueError."""
    with pytest.raises(ValueError, match="https or http"):
        _normalize_base_url("ftp://example.com")


def test_normalize_base_url_rejects_http_for_remote_host() -> None:
    """Cover lines 58-59: http with non-localhost host raises ValueError."""
    with pytest.raises(ValueError, match="localhost"):
        _normalize_base_url("http://example.com/v1")


def test_normalize_base_url_rejects_unexpected_https_path() -> None:
    """Cover line 58: https URL with unexpected path (not empty, /, /v1) raises."""
    with pytest.raises(ValueError, match="empty path or /v1"):
        _normalize_base_url("https://example.com/api")


# --------------------------------------------------------------------------- #
# Network-layer error paths (lines 164-165, 171-172, 176-177, 180)           #
# --------------------------------------------------------------------------- #


def test_client_raises_on_os_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover lines 164-165: OSError during urlopen raises LiteLLMError."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        raise OSError("connection refused")

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("Hi")

    assert excinfo.value.status == -1
    assert "connection refused" in str(excinfo.value).lower()


def test_client_raises_on_non_2xx_status(monkeypatch: pytest.MonkeyPatch) -> None:
    """Cover lines 171-172: non-2xx status code from urlopen raises LiteLLMError."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps({"error": {"message": "service unavailable"}}).encode("utf-8")
        return FakeResponse(body, status=503)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("Hi")

    assert excinfo.value.status == 503


def test_client_raises_on_invalid_json_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover lines 176-177: invalid JSON from server raises LiteLLMError."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        return FakeResponse(b"not valid json", status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("Hi")

    assert "invalid json" in str(excinfo.value).lower()


def test_client_raises_on_non_dict_json_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 180: JSON that is not a dict raises LiteLLMError."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        return FakeResponse(b"[1,2,3]", status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("Hi")

    assert "unexpected" in str(excinfo.value).lower()


# --------------------------------------------------------------------------- #
# _extract_error_message: json parse failure and no-match fallback            #
# --------------------------------------------------------------------------- #


def test_extract_error_message_returns_generic_when_body_is_not_json() -> None:
    """Cover lines 191-192: non-JSON body falls back to generic message."""
    from litellm_example.client import LiteLLMClient

    msg = LiteLLMClient._extract_error_message("not json at all")
    assert "error" in msg.lower()


def test_extract_error_message_returns_generic_when_no_matching_key() -> None:
    """Cover line 200: JSON body with no usable message key falls back."""
    from litellm_example.client import LiteLLMClient

    msg = LiteLLMClient._extract_error_message(json.dumps({"error": {"code": 500}}))
    assert "error" in msg.lower()


# --------------------------------------------------------------------------- #
# _extract_content: error path coverage (lines 207, 213, 219)                #
# --------------------------------------------------------------------------- #


def test_extract_content_raises_when_no_choices(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 207: empty choices list raises LiteLLMError."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        return FakeResponse(json.dumps({"choices": []}).encode(), status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("No choices")

    assert "choices" in str(excinfo.value).lower()


def test_extract_content_raises_when_choice_is_not_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 213: choice that is not a dict raises LiteLLMError."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        return FakeResponse(
            json.dumps({"choices": ["not a dict"]}).encode(), status=200
        )

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("Bad choice")

    assert "choice" in str(excinfo.value).lower()


def test_extract_content_raises_when_message_is_not_dict(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 219: message field that is not a dict raises LiteLLMError."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps({"choices": [{"message": "just a string"}]}).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_chat_completion("Bad message")

    assert "message" in str(excinfo.value).lower()


# --------------------------------------------------------------------------- #
# _extract_response_content: non-dict items coverage (lines 261,264,267,269) #
# --------------------------------------------------------------------------- #


def test_responses_api_skips_non_dict_output_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 261: non-dict output[] items are skipped."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {
                "output": [
                    "not a dict",  # must be skipped
                    {"content": [{"type": "output_text", "text": "real answer"}]},
                ]
            }
        ).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_response("Non-dict output item")  # type: ignore[attr-defined]

    assert text == "real answer"


def test_responses_api_skips_non_list_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 264: content that is not a list is skipped, falls through to error."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {
                "output": [
                    {"content": "not a list"},
                    {"content": [{"type": "output_text", "text": "fallback answer"}]},
                ]
            }
        ).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_response("Non-list content")  # type: ignore[attr-defined]

    assert text == "fallback answer"


def test_responses_api_skips_non_dict_content_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 267: non-dict content blocks are skipped."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {
                "output": [
                    {
                        "content": [
                            "not a dict block",  # must be skipped
                            {"type": "output_text", "text": "block answer"},
                        ]
                    }
                ]
            }
        ).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_response("Non-dict block")  # type: ignore[attr-defined]

    assert text == "block answer"


def test_responses_api_skips_wrong_type_blocks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 269: blocks with unrecognised type are skipped."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {
                "output": [
                    {
                        "content": [
                            {"type": "reasoning", "text": "should be ignored"},
                            {"type": "output_text", "text": "correct answer"},
                        ]
                    }
                ]
            }
        ).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_response("Wrong type block")  # type: ignore[attr-defined]

    assert text == "correct answer"


def test_responses_api_collects_plain_string_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 272: plain string text field is appended to parts."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {"output": [{"content": [{"type": "output_text", "text": "plain str"}]}]}
        ).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    text = c.create_response("Plain string text")  # type: ignore[attr-defined]

    assert text == "plain str"


def test_responses_api_raises_when_all_blocks_skipped(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cover line 281: no usable parts after traversal raises LiteLLMError."""

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        body = json.dumps(
            {"output": [{"content": [{"type": "reasoning", "text": "ignored"}]}]}
        ).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="o3-deep-research")
    with pytest.raises(LiteLLMError) as excinfo:
        c.create_response("All blocks skipped")  # type: ignore[attr-defined]

    assert excinfo.value.status == 200
    assert "usable" in str(excinfo.value).lower()


# --------------------------------------------------------------------------- #
# web_search_preview tool support                                             #
# --------------------------------------------------------------------------- #


def test_responses_api_includes_tools_when_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tools=[...] is forwarded in the request body."""
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        captured["body"] = json.loads(req.data.decode("utf-8"))  # type: ignore[attr-defined]
        body = json.dumps({"output_text": "search result"}).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="gpt-4o")
    text = c.create_response(
        "짜장면의 역사",
        tools=[{"type": "web_search_preview"}],
    )

    assert text == "search result"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["tools"] == [{"type": "web_search_preview"}]


def test_responses_api_omits_tools_when_none(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """tools is NOT included in the request body when None."""
    captured: dict[str, object] = {}

    def fake_urlopen(req, timeout=None, context=None):  # type: ignore[override]
        captured["body"] = json.loads(req.data.decode("utf-8"))  # type: ignore[attr-defined]
        body = json.dumps({"output_text": "no-tools result"}).encode()
        return FakeResponse(body, status=200)

    from litellm_example import client as client_module

    monkeypatch.setattr(client_module.request, "urlopen", fake_urlopen)

    c = LiteLLMClient("https://example.com", "sk-test", model="gpt-4o")
    c.create_response("Hello", tools=None)

    assert "tools" not in captured["body"]
