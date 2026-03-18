from __future__ import annotations

from pathlib import Path

import pytest

from litellm_relay.__main__ import build_hypercorn_config
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

    settings = load_settings(dotenv_path=dotenv)

    assert settings.base_url == "https://from-env.example/v1"
    assert settings.api_key == "sk-from-env"
    assert settings.model == "custom-model"
    assert settings.host == "relay.local"
    assert settings.port == 8181
    assert settings.timeout_seconds == 12.5


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
