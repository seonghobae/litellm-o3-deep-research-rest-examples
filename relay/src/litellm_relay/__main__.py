"""LiteLLM 릴레이 서버 CLI 진입점을 제공한다."""

from __future__ import annotations

import argparse
import asyncio
import sys

from hypercorn.asyncio import serve
from hypercorn.config import Config

from .app import create_app
from .config import RelaySettings, load_settings


def build_hypercorn_config(settings: RelaySettings) -> Config:
    """설정의 호스트와 포트에 바인드되는 Hypercorn 설정을 만든다."""
    config = Config()
    config.bind = [f"{settings.host}:{settings.port}"]
    return config


def _build_parser() -> argparse.ArgumentParser:
    """릴레이 CLI 인자 파서를 구성한다."""
    return argparse.ArgumentParser(description="Run the LiteLLM relay example server.")


def main(argv: list[str] | None = None) -> int:
    """릴레이 애플리케이션을 실행하는 CLI 진입점이다."""
    _build_parser().parse_args(sys.argv[1:] if argv is None else argv)
    settings = load_settings()
    app = create_app(settings=settings)
    config = build_hypercorn_config(settings)
    asyncio.run(serve(app, config))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper
    raise SystemExit(main())
