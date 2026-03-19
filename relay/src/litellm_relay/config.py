from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class RelaySettings:
    """Resolved configuration for the relay example."""

    base_url: str
    api_key: str
    model: str = "o3-deep-research"
    host: str = "127.0.0.1"
    port: int = 8080
    timeout_seconds: float = 30.0
    chat_model: str = "gpt-4o"


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


_SENTINEL = object()


def load_settings(
    dotenv_path: Path | None = _SENTINEL,  # type: ignore[assignment]
    *,
    env_file: Path | None = _SENTINEL,  # type: ignore[assignment]
) -> RelaySettings:
    """Load relay settings from env vars and an optional ``~/.env`` file.

    Environment variables always take precedence; the dotenv file is only read
    when the variable is absent from the real environment.  Raises
    ``RuntimeError`` if ``LITELLM_BASE_URL`` or ``LITELLM_API_KEY`` remain
    unset after loading.

    Parameters
    ----------
    dotenv_path:
        Path to the ``.env`` file.  Defaults to ``~/.env`` when not provided.
        Pass ``None`` explicitly to skip dotenv loading entirely.
    env_file:
        Alias for *dotenv_path*.  Takes precedence when both are supplied.
    """
    # Resolve which value to use: env_file takes precedence over dotenv_path.
    if env_file is not _SENTINEL:
        resolved_path: Path | None = env_file  # type: ignore[assignment]
    elif dotenv_path is not _SENTINEL:
        resolved_path = dotenv_path  # type: ignore[assignment]
    else:
        resolved_path = Path.home() / ".env"

    if resolved_path is None:
        # Caller explicitly passed None — skip dotenv loading.
        pass
    elif resolved_path.is_file():
        load_dotenv(dotenv_path=resolved_path, override=False)

    base_url = os.getenv("LITELLM_BASE_URL")
    api_key = os.getenv("LITELLM_API_KEY")
    model = os.getenv("LITELLM_MODEL", "o3-deep-research")
    host = os.getenv("RELAY_HOST", "127.0.0.1")
    port = os.getenv("RELAY_PORT", "8080")
    timeout_seconds = os.getenv("RELAY_TIMEOUT_SECONDS", "30")
    chat_model = os.getenv("LITELLM_CHAT_MODEL", "gpt-4o")

    if _is_blank(base_url):
        raise RuntimeError(
            "LITELLM_BASE_URL is not set. Configure it in the environment or ~/.env."
        )
    if _is_blank(api_key):
        raise RuntimeError(
            "LITELLM_API_KEY is not set. Configure it in the environment or ~/.env."
        )

    return RelaySettings(
        base_url=base_url.strip(),
        api_key=api_key.strip(),
        model=(model or "").strip() or "o3-deep-research",
        host=(host or "").strip() or "127.0.0.1",
        port=int((port or "").strip() or "8080"),
        timeout_seconds=float((timeout_seconds or "").strip() or "30"),
        chat_model=(chat_model or "").strip() or "gpt-4o",
    )
