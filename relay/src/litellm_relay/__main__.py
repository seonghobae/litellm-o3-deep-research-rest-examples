from __future__ import annotations

import asyncio

from hypercorn.asyncio import serve
from hypercorn.config import Config

from .app import create_app
from .config import RelaySettings, load_settings


def build_hypercorn_config(settings: RelaySettings) -> Config:
    """Build a Hypercorn ``Config`` that binds to the host and port in *settings*."""
    config = Config()
    config.bind = [f"{settings.host}:{settings.port}"]
    return config


def main() -> int:
    """Entrypoint for ``python -m litellm_relay`` and the ``litellm-relay`` script."""
    settings = load_settings()
    app = create_app(settings=settings)
    config = build_hypercorn_config(settings)
    asyncio.run(serve(app, config))
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper
    raise SystemExit(main())
