"""LiteLLM 예제 클라이언트 설정 로딩을 담당한다."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """LiteLLM 프록시 호출에 필요한 해석된 설정이다."""

    base_url: str
    api_key: str
    model: str = "o3-deep-research"


def _is_blank(value: str | None) -> bool:
    """값이 없거나 공백뿐인지 확인한다."""
    return value is None or not value.strip()


def load_settings(dotenv_path: Path | None = None) -> Settings:
    """환경 변수와 선택적 ``~/.env`` 파일에서 설정을 읽어온다."""

    if dotenv_path is None:
        dotenv_path = Path.home() / ".env"

    # Only attempt to load ~/.env if it exists, and never override real env vars
    if dotenv_path.is_file():
        load_dotenv(dotenv_path=dotenv_path, override=False)

    base_url = os.getenv("LITELLM_BASE_URL")
    api_key = os.getenv("LITELLM_API_KEY")
    model = os.getenv("LITELLM_MODEL", "o3-deep-research")

    if _is_blank(base_url):
        raise RuntimeError(
            "LITELLM_BASE_URL is not set. Configure it in the environment or ~/.env."
        )

    if _is_blank(api_key):
        raise RuntimeError(
            "LITELLM_API_KEY is not set. Configure it in the environment or ~/.env."
        )

    # Normalise whitespace while preserving non-empty values
    base_url = base_url.strip()
    api_key = api_key.strip()
    model = (model or "o3-deep-research").strip() or "o3-deep-research"

    return Settings(base_url=base_url, api_key=api_key, model=model)
