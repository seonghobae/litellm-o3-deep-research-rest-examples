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


def _is_blank(value: str | None) -> bool:
    return value is None or not value.strip()


def load_settings(dotenv_path: Path | None = None) -> RelaySettings:
    """Load relay settings from env vars and an optional ~/.env file."""

    if dotenv_path is None:
        dotenv_path = Path.home() / ".env"

    if dotenv_path.is_file():
        load_dotenv(dotenv_path=dotenv_path, override=False)

    base_url = os.getenv("LITELLM_BASE_URL")
    api_key = os.getenv("LITELLM_API_KEY")
    model = os.getenv("LITELLM_MODEL", "o3-deep-research")
    host = os.getenv("RELAY_HOST", "127.0.0.1")
    port = os.getenv("RELAY_PORT", "8080")
    timeout_seconds = os.getenv("RELAY_TIMEOUT_SECONDS", "30")

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
        model=(model or "o3-deep-research").strip() or "o3-deep-research",
        host=(host or "127.0.0.1").strip() or "127.0.0.1",
        port=int((port or "8080").strip() or "8080"),
        timeout_seconds=float((timeout_seconds or "30").strip() or "30"),
    )
