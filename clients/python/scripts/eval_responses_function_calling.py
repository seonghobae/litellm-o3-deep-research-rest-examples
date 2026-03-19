#!/usr/bin/env python3
"""Evaluate whether the Responses API supports function calling via LiteLLM Proxy.

This script tests whether ``POST /v1/responses`` with a function tool attached
produces a tool call or raises an error. Results feed the evaluation matrix
in docs/ko/auto-toolcalling.md.

Run:
  cd clients/python
  LITELLM_MODEL=gpt-4o \\
  LITELLM_BASE_URL=https://your-litellm-host/v1 \\
  LITELLM_API_KEY=sk-your-key \\
  uv run python scripts/eval_responses_function_calling.py
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, "src")

from litellm_example.client import (
    DEEP_RESEARCH_FUNCTION_TOOL,
    LiteLLMClient,
    LiteLLMError,
)


def main() -> None:
    base_url = os.environ.get("LITELLM_BASE_URL", "")
    api_key = os.environ.get("LITELLM_API_KEY", "")
    model = os.environ.get("LITELLM_MODEL", "gpt-4o")

    if not base_url or not api_key:
        print(
            "ERROR: LITELLM_BASE_URL and LITELLM_API_KEY must be set.", file=sys.stderr
        )
        sys.exit(1)

    client = LiteLLMClient(base_url, api_key, model, timeout=60.0)

    print(f"Testing Responses API function calling with model={model}")
    print(f"Endpoint: {client._responses_url()}")
    print()

    payload = {
        "model": model,
        "input": "짜장면의 역사를 자세히 설명해줘",
        "tools": [DEEP_RESEARCH_FUNCTION_TOOL],
    }

    try:
        result = client._post_json(client._responses_url(), payload)
        print("SUCCESS — Raw response (first 800 chars):")
        print(json.dumps(result, ensure_ascii=False, indent=2)[:800])

        # Inspect output for tool_calls
        output = result.get("output") or []
        has_tool_call = any(
            item.get("type") == "function_call"
            for item in output
            if isinstance(item, dict)
        )
        print()
        print(f"tool_call found in output: {has_tool_call}")
        print(f"status: {result.get('status', 'unknown')}")
    except LiteLLMError as exc:
        print(f"FAIL — HTTP {exc.status}: {exc}")
        if exc.body:
            print(f"Body: {exc.body[:400]}")


if __name__ == "__main__":
    main()
