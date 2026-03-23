from __future__ import annotations

import pytest

from litellm_example.__main__ import main
from litellm_example.client import LiteLLMClient, LiteLLMError, ToolCallingResult
from litellm_example.config import Settings


def _make_settings() -> Settings:
    return Settings(
        base_url="https://localhost:4000/v1",
        api_key="sk-test",
        model="o3-deep-research",
    )


def test_main_calls_chat_completion_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, object] = {}

    def fake_create_chat_completion(self: LiteLLMClient, prompt: str) -> str:
        captured["api"] = "chat"
        captured["prompt"] = prompt
        return "chat answer"

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(
        LiteLLMClient, "create_chat_completion", fake_create_chat_completion
    )

    exit_code = main(["my prompt"])

    assert exit_code == 0
    assert captured["api"] == "chat"
    assert captured["prompt"] == "my prompt"


def test_main_uses_default_prompt_when_none_provided(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_chat_completion(self: LiteLLMClient, prompt: str) -> str:
        captured["prompt"] = prompt
        return "ok"

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(
        LiteLLMClient, "create_chat_completion", fake_create_chat_completion
    )

    exit_code = main([])

    assert exit_code == 0
    assert "o3-deep-research" in captured["prompt"]


def test_main_calls_responses_api_when_requested(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_response(
        self: LiteLLMClient,
        prompt: str,
        background: bool = False,
        tools: object = None,
    ) -> str:
        captured["api"] = "responses"
        captured["background"] = background
        captured["tools"] = tools
        return "responses answer"

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(LiteLLMClient, "create_response", fake_create_response)

    exit_code = main(["--api", "responses", "my question"])

    assert exit_code == 0
    assert captured["api"] == "responses"
    assert captured["background"] is False
    assert captured["tools"] is None


def test_main_passes_background_flag_to_responses_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_response(
        self: LiteLLMClient,
        prompt: str,
        background: bool = False,
        tools: object = None,
    ) -> str:
        captured["background"] = background
        return '{"id": "resp_1", "status": "queued"}'

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(LiteLLMClient, "create_response", fake_create_response)

    exit_code = main(["--api", "responses", "--background", "queue this"])

    assert exit_code == 0
    assert captured["background"] is True


def test_main_returns_1_when_background_used_without_responses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )

    exit_code = main(["--background", "my prompt"])

    assert exit_code == 1


def test_main_returns_1_on_litellm_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def raise_error(self: LiteLLMClient, prompt: str) -> str:
        raise LiteLLMError(500, "upstream error")

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(LiteLLMClient, "create_chat_completion", raise_error)

    exit_code = main(["prompt"])

    assert exit_code == 1


def test_main_returns_1_when_settings_load_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def raise_runtime(dotenv_path=None) -> Settings:
        raise RuntimeError("LITELLM_BASE_URL is not set.")

    monkeypatch.setattr("litellm_example.__main__.load_settings", raise_runtime)

    exit_code = main(["prompt"])

    assert exit_code == 1


def test_main_passes_custom_timeout_to_client(monkeypatch: pytest.MonkeyPatch) -> None:
    """--timeout is forwarded to LiteLLMClient as the timeout parameter."""
    captured: dict[str, object] = {}

    original_init = LiteLLMClient.__init__

    def fake_init(
        self: LiteLLMClient,
        base_url: str,
        api_key: str,
        model: str,
        timeout: float = 30.0,
    ) -> None:
        captured["timeout"] = timeout
        original_init(self, base_url, api_key, model, timeout=timeout)

    def fake_create_chat_completion(self: LiteLLMClient, prompt: str) -> str:
        return "ok"

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(LiteLLMClient, "__init__", fake_init)
    monkeypatch.setattr(
        LiteLLMClient, "create_chat_completion", fake_create_chat_completion
    )

    exit_code = main(["--timeout", "120", "my prompt"])

    assert exit_code == 0
    assert captured["timeout"] == 120.0


def test_main_passes_web_search_tool_to_responses_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--web-search attaches web_search_preview tool to the responses call."""
    captured: dict[str, object] = {}

    def fake_create_response(
        self: LiteLLMClient,
        prompt: str,
        background: bool = False,
        tools: object = None,
    ) -> str:
        captured["tools"] = tools
        return "web search answer"

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(LiteLLMClient, "create_response", fake_create_response)

    exit_code = main(["--api", "responses", "--web-search", "짜장면의 역사를 검색해줘"])

    assert exit_code == 0
    assert isinstance(captured["tools"], list)
    assert captured["tools"][0]["type"] == "web_search_preview"


def test_main_rejects_web_search_without_responses_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--web-search without --api responses must fail fast."""
    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )

    exit_code = main(["--web-search", "some prompt"])

    assert exit_code == 1


# --------------------------------------------------------------------------- #
# --auto-tool-call flag tests                                                  #
# --------------------------------------------------------------------------- #


def test_main_auto_tool_call_calls_create_response_with_tool_calling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--auto-tool-call invokes create_response_with_tool_calling on the client."""
    captured: dict[str, object] = {}

    def fake_create_response_with_tool_calling(
        self: LiteLLMClient, prompt: str, relay_base_url: str | None = None
    ) -> ToolCallingResult:
        captured["prompt"] = prompt
        captured["relay_base_url"] = relay_base_url
        return ToolCallingResult(final_text="tool answer", tool_called=False)

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(
        LiteLLMClient,
        "create_response_with_tool_calling",
        fake_create_response_with_tool_calling,
    )

    exit_code = main(["--auto-tool-call", "my research question"])

    assert exit_code == 0
    assert captured["prompt"] == "my research question"


def test_main_auto_tool_call_prints_stderr_when_tool_called(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """When tool_called=True, prints only a generic stderr notice."""

    def fake_create_response_with_tool_calling(
        self: LiteLLMClient, prompt: str, relay_base_url: str | None = None
    ) -> ToolCallingResult:
        return ToolCallingResult(
            final_text="research result",
            tool_called=True,
            response_id="resp_2",
            previous_response_id="resp_1",
            tool_call_id="call_1",
            invocation_id="inv_1",
            upstream_response_id="up_1",
        )

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(
        LiteLLMClient,
        "create_response_with_tool_calling",
        fake_create_response_with_tool_calling,
    )

    exit_code = main(["--auto-tool-call", "what is the history of jjajangmyeon"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "research result" in captured.out
    assert "[deep_research was called automatically]" in captured.err
    assert "resp_2" not in captured.err
    assert "resp_1" not in captured.err
    assert "call_1" not in captured.err
    assert "inv_1" not in captured.err
    assert "up_1" not in captured.err


def test_main_auto_tool_call_no_stderr_when_tool_not_called(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    """When tool_called=False, does NOT print to stderr."""

    def fake_create_response_with_tool_calling(
        self: LiteLLMClient, prompt: str, relay_base_url: str | None = None
    ) -> ToolCallingResult:
        return ToolCallingResult(final_text="direct answer", tool_called=False)

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(
        LiteLLMClient,
        "create_response_with_tool_calling",
        fake_create_response_with_tool_calling,
    )

    exit_code = main(["--auto-tool-call", "simple question"])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "direct answer" in captured.out
    assert "[deep_research was called automatically]" not in captured.err


def test_main_auto_tool_call_uses_relay_base_url_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RELAY_BASE_URL env var is passed as relay_base_url to create_response_with_tool_calling."""
    captured: dict[str, object] = {}

    def fake_create_response_with_tool_calling(
        self: LiteLLMClient, prompt: str, relay_base_url: str | None = None
    ) -> ToolCallingResult:
        captured["relay_base_url"] = relay_base_url
        return ToolCallingResult(final_text="ok", tool_called=False)

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(
        LiteLLMClient,
        "create_response_with_tool_calling",
        fake_create_response_with_tool_calling,
    )
    monkeypatch.setenv("RELAY_BASE_URL", "http://relay.internal:9090")

    exit_code = main(["--auto-tool-call", "query"])

    assert exit_code == 0
    assert captured["relay_base_url"] == "http://relay.internal:9090"


def test_main_auto_tool_call_returns_1_on_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """--auto-tool-call returns exit code 1 when create_response_with_tool_calling raises."""

    def fake_create_response_with_tool_calling(
        self: LiteLLMClient, prompt: str, relay_base_url: str | None = None
    ) -> ToolCallingResult:
        raise LiteLLMError(500, "relay error")

    monkeypatch.setattr(
        "litellm_example.__main__.load_settings",
        lambda dotenv_path=None: _make_settings(),
    )
    monkeypatch.setattr(
        LiteLLMClient,
        "create_response_with_tool_calling",
        fake_create_response_with_tool_calling,
    )

    exit_code = main(["--auto-tool-call", "some query"])

    assert exit_code == 1
