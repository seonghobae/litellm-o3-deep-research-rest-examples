# Acceptance criteria

Work in this repository is complete only when all of the following are true:

1. The Python example can load `LITELLM_API_KEY` and `LITELLM_BASE_URL` from the environment or `~/.env` and call `o3-deep-research` via both `chat/completions` and `responses` REST APIs.
2. The Java example can load the same configuration and call `o3-deep-research` via both APIs.
3. The relay example can load the same upstream LiteLLM settings plus `RELAY_HOST`, `RELAY_PORT`, and `RELAY_TIMEOUT_SECONDS`, and it exposes a structured `tool-invocations` contract over FastAPI + Hypercorn.
4. The Java example can call the relay via `RELAY_BASE_URL` in foreground, background, and stream modes without leaking raw upstream `input` payloads in the public contract.
5. Direct clients still support `responses` requests with `background: true` and return raw response metadata when background mode is used.
6. Automated tests cover configuration loading, request construction, background handling, status polling, SSE text streaming, and error handling across Python, Java, and relay code.
7. Root documentation explains how to run the direct clients and relay example, how background responses differ from foreground CLI execution, and how to avoid committing secrets.
8. Korean user-facing manuals are present and GitHub Pages-publishable.
9. The docs site builds successfully with `mkdocs build --strict`.
10. Local verification includes:
    - `cd clients/python && uv sync --all-extras --dev && uv run pytest`
    - `cd clients/java && mvn test`
    - `cd relay && uv sync --all-extras --dev && uv run pytest`
    - `mkdocs build --strict`
11. If live credentials are available, at least one successful direct foreground call is observed in both languages, at least one successful `background: true` submission is observed in both direct clients, and at least one successful relay invocation is observed before the work is declared complete.
