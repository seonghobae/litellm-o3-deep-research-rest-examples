from __future__ import annotations

import pytest

from litellm_example.__main__ import main
from litellm_example.client import LiteLLMClient, LiteLLMError
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
        self: LiteLLMClient, prompt: str, background: bool = False
    ) -> str:
        captured["api"] = "responses"
        captured["background"] = background
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


def test_main_passes_background_flag_to_responses_api(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_create_response(
        self: LiteLLMClient, prompt: str, background: bool = False
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
