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
        "--api",
        choices=("chat", "responses"),
        default="chat",
        help="Which OpenAI-compatible endpoint to use.",
    )
    parser.add_argument(
        "--background",
        action="store_true",
        help="Request server-side background processing for the responses API.",
    )
    parser.add_argument(
        "--web-search",
        action="store_true",
        dest="web_search",
        help=(
            "Attach the web_search_preview tool to a responses API call.  "
            "Requires --api responses.  Enables real-time web search on "
            "models that support it (e.g. gpt-4o)."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=30.0,
        help="Request timeout in seconds (default: 30).  "
        "Increase for long-running models like o3-deep-research.",
    )
    parser.add_argument(
        "prompt",
        nargs="?",
        default="Explain what the o3-deep-research model is useful for.",
        help="User prompt to send to the model.",
    )

    args = parser.parse_args(argv)

    try:
        if args.background and args.api != "responses":
            raise ValueError("--background can only be used with --api responses.")
        if args.web_search and args.api != "responses":
            raise ValueError("--web-search can only be used with --api responses.")

        settings = load_settings()
        client = LiteLLMClient(
            settings.base_url,
            settings.api_key,
            settings.model,
            timeout=args.timeout,
        )
        if args.api == "responses":
            tools = [{"type": "web_search_preview"}] if args.web_search else None
            content = client.create_response(
                args.prompt, background=args.background, tools=tools
            )
        else:
            content = client.create_chat_completion(args.prompt)
    except (RuntimeError, ValueError, LiteLLMError) as exc:
        # Never print secrets; rely on the exception message only.
        print(f"Error: {exc}", file=sys.stderr)
        return 1

    print(content)
    return 0


if __name__ == "__main__":  # pragma: no cover - thin CLI wrapper
    raise SystemExit(main())
