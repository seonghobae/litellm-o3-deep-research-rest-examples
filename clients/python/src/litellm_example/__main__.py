from __future__ import annotations

import argparse
import sys

from .config import load_settings
from .client import LiteLLMClient, LiteLLMError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Call a LiteLLM o3-deep-research model via REST.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Explain what the o3-deep-research model is useful for.",
        help="User prompt to send to the model.",
    )

    args = parser.parse_args(argv)

    try:
        settings = load_settings()
        client = LiteLLMClient(settings.base_url, settings.api_key, settings.model)
        content = client.create_chat_completion(args.prompt)
    except (RuntimeError, ValueError, LiteLLMError) as exc:
        # Never print secrets; rely on the exception message only.
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(content)
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper
    raise SystemExit(main())
