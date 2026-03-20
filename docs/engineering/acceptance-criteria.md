# Acceptance criteria

Work in this repository is complete only when all of the following are true:

## Core client functionality

1. The Python example can load `LITELLM_API_KEY` and `LITELLM_BASE_URL` from the environment or `~/.env` and call `o3-deep-research` via both `chat/completions` and `responses` REST APIs.
2. The Java example can load the same configuration and call `o3-deep-research` via both APIs.
3. Both Python and Java direct clients support `--timeout <seconds>` to control request timeout for long-running models.

## Background and streaming

4. Direct clients support `responses` requests with `background: true` and return raw response metadata (id, status) when background mode is used.
5. The relay example exposes `GET /api/v1/tool-invocations/{id}/events` as a text-focused SSE stream, and `GET /api/v1/tool-invocations/{id}/wait` for synchronous polling until completion.

## Relay / tool-invocations contract

6. The relay example can load upstream LiteLLM settings (`LITELLM_BASE_URL`, `LITELLM_API_KEY`, `LITELLM_MODEL`) plus relay settings (`RELAY_HOST`, `RELAY_PORT`, `RELAY_TIMEOUT_SECONDS`, `RELAY_RESEARCH_TIMEOUT_SECONDS`, `LITELLM_CHAT_MODEL`), and exposes a structured `tool-invocations` contract over FastAPI + Hypercorn.
7. The Java example can call the relay via `RELAY_BASE_URL` in foreground, background, and stream modes without leaking raw upstream `input` payloads in the public contract.
8. The relay `DeepResearchArguments` contract supports: `research_question`, `context`, `constraints`, `deliverable_format`, `require_citations`, `background`, `stream`, `system_prompt`, and `text_format`.

## web_search_preview

9. Both Python (`--web-search`) and Java (`--web-search`) CLI tools support attaching `web_search_preview` to Responses API calls, enabling real-time web search on supporting models (e.g. gpt-4o).

## system_prompt

10. The relay wrapper forwards `system_prompt` to the Responses API `instructions` field, separating model-level directives from the research question. Both `invoke_deep_research()` and `stream_deep_research()` pass `instructions` when `system_prompt` is set.

## text_format (structured output)

11. The relay wrapper supports `text_format` (`json_object` or `json_schema`) mapped to the Responses API `text.format` field for machine-readable JSON output. gpt-4o fully supports both; o3-deep-research does not support `json_schema` (API 400).

## Auto tool-calling (function calling)

12. Python and Java direct clients support `--auto-tool-call` flag using the Responses API function-calling flow: 1st `POST /v1/responses` with the `deep_research` function schema → relay `POST /api/v1/tool-invocations` execution → 2nd `POST /v1/responses` with `previous_response_id` and `function_call_output`.
13. The relay exposes `POST /api/v1/chat` which internally performs relay-side orchestration using the Responses API: 1st Responses turn → `function_call` detection → deep_research execution → 2nd Responses turn → structured `ChatResponse`. The relay uses `LITELLM_CHAT_MODEL` (default `gpt-4o`) for orchestration turns and `LITELLM_MODEL` for deep research.
14. The relay `ChatOrchestrator` uses separate timeouts: `RELAY_TIMEOUT_SECONDS` (default 30 s) for Responses orchestration turns and `RELAY_RESEARCH_TIMEOUT_SECONDS` (default 300 s) for deep_research execution.
15. Upstream errors in auto tool-calling are caught and returned as a structured `ChatResponse` (not bare HTTP 500), and the public payload does not include raw upstream exception text.

## Tests and coverage

16. Automated tests cover: configuration loading, request construction, background handling, status polling, SSE text streaming, error handling, redacted relay error payloads, `system_prompt` passthrough, `text_format` passthrough, `web_search_preview` passthrough, `auto_tool_call` (no-tool and tool-call paths), `ChatOrchestrator` timeout separation, and Pydantic tool_call normalisation.
17. Python relay: `uv run pytest --cov=litellm_relay --cov-fail-under=100` passes.
18. Python client: `uv run pytest --cov=litellm_example --cov-fail-under=100` passes.
19. Java: `mvn test` → BUILD SUCCESS.

## Documentation

20. Korean user-facing manuals cover: all CLI flags (`--api`, `--background`, `--web-search`, `--auto-tool-call`, `--timeout`, `--target`, `--stream`, `--deliverable-format`), relay API contract, auto tool-calling guide, system_prompt guide, text_format guide, timeout configuration, and live verification results.
21. `python-example.md`, `java-example.md`, `quickstart.md`, `responses-guide.md`, `faq.md`, and `relay-example.md` accurately reflect the current feature set.
22. `docs/engineering/acceptance-criteria.md` (this file) is current.
23. The docs site builds successfully with `mkdocs build --strict`.

## Live verification

24. If live credentials are available, at minimum the following are verified before declaring work complete:
    - Python `chat` and `responses` foreground (direct)
    - Python `responses --background` submission (direct)
    - Java `chat` and `responses` foreground (direct)
    - Java `responses --background` submission (direct)
    - Relay foreground tool-invocation
    - Relay background submission
    - Relay `--auto-tool-call` / `/api/v1/chat` with tool-calling topic (tool_called=true)
    - Relay `/api/v1/chat` with non-research topic (tool_called=false)
    - Python `--web-search` (web search result returned)
    - Python `--auto-tool-call` (relay invoked automatically)
    - Java `--auto-tool-call` (relay invoked automatically)
