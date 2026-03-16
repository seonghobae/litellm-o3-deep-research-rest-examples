from __future__ import annotations

from pathlib import Path

import pytest

from litellm_example.config import Settings, load_settings


def test_reads_from_dotenv_when_env_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "LITELLM_BASE_URL=https://example.com\nLITELLM_API_KEY=sk-from-file\n",
        encoding="utf-8",
    )

    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)

    settings = load_settings(dotenv_path=dotenv)
    assert isinstance(settings, Settings)
    assert settings.base_url == "https://example.com"
    assert settings.api_key == "sk-from-file"
    assert settings.model == "o3-deep-research"  # default


def test_env_vars_take_precedence_over_dotenv(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    dotenv = tmp_path / ".env"
    dotenv.write_text(
        "LITELLM_BASE_URL=https://from-dotenv.example\n"
        "LITELLM_API_KEY=sk-from-dotenv\n",
        encoding="utf-8",
    )

    monkeypatch.setenv("LITELLM_BASE_URL", " https://from-env.example ")
    monkeypatch.setenv("LITELLM_API_KEY", " sk-from-env ")
    monkeypatch.setenv("LITELLM_MODEL", "custom-model")

    settings = load_settings(dotenv_path=dotenv)
    assert settings.base_url == "https://from-env.example"
    assert settings.api_key == "sk-from-env"
    assert settings.model == "custom-model"


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

    message = str(excinfo.value)
    assert var_name.lower() in message.lower()
