"""LiteLLM 예제 클라이언트 CLI 진입점을 제공한다."""

from __future__ import annotations

import argparse
import json
import os
import sys

from .config import load_settings
from .client import LiteLLMClient, LiteLLMError


def main(argv: list[str] | None = None) -> int:
    """명령줄 인자를 파싱해 LiteLLM 요청을 실행한다."""
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
        "--auto-tool-call",
        action="store_true",
        dest="auto_tool_call",
        help=(
            "Use OpenAI-standard Responses API function calling with the "
            "deep_research tool. When the model decides to call "
            "deep_research, the relay server executes the research via "
            "tool-invocations and the client sends a function_call_output "
            "continuation automatically. "
            "Cannot be combined with --target relay."
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
        if args.auto_tool_call:
            relay_url = os.environ.get("RELAY_BASE_URL", "http://127.0.0.1:8080")
            result = client.create_response_with_tool_calling(
                args.prompt, relay_base_url=relay_url
            )
            print(result.final_text)
            if result.tool_called:
                print("[deep_research was called automatically]", file=sys.stderr)
                debug = {
                    "response_id": result.response_id,
                    "previous_response_id": result.previous_response_id,
                    "tool_call_id": result.tool_call_id,
                    "invocation_id": result.invocation_id,
                    "upstream_response_id": result.upstream_response_id,
                }
                print(json.dumps(debug, ensure_ascii=False), file=sys.stderr)
            return 0
        elif args.api == "responses":
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
