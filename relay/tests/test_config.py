from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from litellm_relay.__main__ import build_hypercorn_config, main
from litellm_relay.config import RelaySettings, load_settings


def test_loads_relay_settings_from_env_and_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "LITELLM_BASE_URL=https://relay-proxy.example\n"
        "LITELLM_API_KEY=sk-from-file\n"
        "RELAY_HOST=0.0.0.0\n"
        "RELAY_PORT=9090\n"
        "RELAY_TIMEOUT_SECONDS=45\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.delenv("LITELLM_MODEL", raising=False)
    monkeypatch.delenv("RELAY_HOST", raising=False)
    monkeypatch.delenv("RELAY_PORT", raising=False)
    monkeypatch.delenv("RELAY_TIMEOUT_SECONDS", raising=False)

    settings = load_settings(dotenv_path=dotenv)

    assert isinstance(settings, RelaySettings)
    assert settings.base_url == "https://relay-proxy.example"
    assert settings.api_key == "sk-from-file"
    assert settings.model == "o3-deep-research"
    assert settings.host == "0.0.0.0"
    assert settings.port == 9090
    assert settings.timeout_seconds == 45.0
    assert settings.max_invocations == 1024
    assert settings.max_stream_bytes == 1_000_000


def test_environment_values_override_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "LITELLM_BASE_URL=https://from-dotenv.example\n"
        "LITELLM_API_KEY=sk-from-dotenv\n"
        "LITELLM_MODEL=from-dotenv-model\n"
        "RELAY_HOST=127.0.0.1\n"
        "RELAY_PORT=8080\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("LITELLM_BASE_URL", " https://from-env.example/v1 ")
    monkeypatch.setenv("LITELLM_API_KEY", " sk-from-env ")
    monkeypatch.setenv("LITELLM_MODEL", "custom-model")
    monkeypatch.setenv("RELAY_HOST", "relay.local")
    monkeypatch.setenv("RELAY_PORT", "8181")
    monkeypatch.setenv("RELAY_TIMEOUT_SECONDS", "12.5")
    monkeypatch.setenv("RELAY_MAX_INVOCATIONS", "77")
    monkeypatch.setenv("RELAY_MAX_STREAM_BYTES", "2048")

    settings = load_settings(dotenv_path=dotenv)

    assert settings.base_url == "https://from-env.example/v1"
    assert settings.api_key == "sk-from-env"
    assert settings.model == "custom-model"
    assert settings.host == "relay.local"
    assert settings.port == 8181
    assert settings.timeout_seconds == 12.5
    assert settings.max_invocations == 77
    assert settings.max_stream_bytes == 2048


@pytest.mark.parametrize("var_name", ["LITELLM_BASE_URL", "LITELLM_API_KEY"])
def test_missing_required_variables_raise(
    var_name: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text("", encoding="utf-8")

    other_var = (
        "LITELLM_API_KEY" if var_name == "LITELLM_BASE_URL" else "LITELLM_BASE_URL"
    )
    monkeypatch.setenv(other_var, "configured")
    monkeypatch.delenv(var_name, raising=False)

    with pytest.raises(RuntimeError) as excinfo:
        load_settings(dotenv_path=dotenv)

    assert var_name.lower() in str(excinfo.value).lower()


def test_main_builds_hypercorn_bind_from_settings() -> None:
    settings = RelaySettings(
        base_url="https://proxy.example/v1",
        api_key="sk-relay",
        model="o3-deep-research",
        host="0.0.0.0",
        port=9090,
        timeout_seconds=30.0,
    )

    config = build_hypercorn_config(settings)

    assert config.bind == ["0.0.0.0:9090"]


def test_main_starts_hypercorn_and_returns_zero(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Verify that main() wires load_settings -> create_app -> serve correctly.

    We do not start a real server; asyncio.run and serve are replaced with
    lightweight stubs.
    """
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "LITELLM_BASE_URL=https://dummy.test/v1\nLITELLM_API_KEY=sk-dummy\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("LITELLM_BASE_URL", "https://dummy.test/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "sk-dummy")

    serve_mock = MagicMock(return_value=AsyncMock())

    with patch("litellm_relay.__main__.serve", serve_mock):
        with patch("litellm_relay.__main__.asyncio.run") as run_mock:
            result = main()

    assert result == 0
    run_mock.assert_called_once()


def test_chat_model_defaults_to_gpt_4o(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_API_KEY", "sk-x")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://h/v1")
    monkeypatch.delenv("LITELLM_CHAT_MODEL", raising=False)
    settings = load_settings(env_file=None)
    assert settings.chat_model == "gpt-4o"


def test_chat_model_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_API_KEY", "sk-x")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://h/v1")
    monkeypatch.setenv("LITELLM_CHAT_MODEL", "gpt-4o-mini")
    settings = load_settings(env_file=None)
    assert settings.chat_model == "gpt-4o-mini"


def test_research_timeout_defaults_to_300(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_API_KEY", "sk-x")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://h/v1")
    monkeypatch.delenv("RELAY_RESEARCH_TIMEOUT_SECONDS", raising=False)
    settings = load_settings(env_file=None)
    assert settings.research_timeout_seconds == 300.0


def test_research_timeout_can_be_overridden(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("LITELLM_API_KEY", "sk-x")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://h/v1")
    monkeypatch.setenv("RELAY_RESEARCH_TIMEOUT_SECONDS", "600")
    settings = load_settings(env_file=None)
    assert settings.research_timeout_seconds == 600.0


def test_memory_limits_default_and_can_be_overridden(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("LITELLM_API_KEY", "sk-x")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://h/v1")
    monkeypatch.delenv("RELAY_MAX_INVOCATIONS", raising=False)
    monkeypatch.delenv("RELAY_MAX_STREAM_BYTES", raising=False)

    default_settings = load_settings(env_file=None)

    assert default_settings.max_invocations == 1024
    assert default_settings.max_stream_bytes == 1_000_000

    monkeypatch.setenv("RELAY_MAX_INVOCATIONS", "12")
    monkeypatch.setenv("RELAY_MAX_STREAM_BYTES", "4096")

    overridden_settings = load_settings(env_file=None)

    assert overridden_settings.max_invocations == 12
    assert overridden_settings.max_stream_bytes == 4096
