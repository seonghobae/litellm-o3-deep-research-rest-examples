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

11. The relay wrapper supports `text_format` (`json_object` or `json_schema`) mapped to the Responses API `text.format` field for machine-readable JSON output. gpt-4o fully supports both; o3-deep-research rejects `json_schema` with API 400, while `json_object` may be accepted at the API layer without guaranteed model compliance.

## Auto tool-calling (function calling)

12. Python and Java direct clients support `--auto-tool-call` flag using the OpenAI-standard Responses API function-calling pattern: the client sends `POST /v1/responses` with the `deep_research` function schema attached; if the model emits a `function_call`, the client executes the tool via relay `POST /api/v1/tool-invocations`, then sends a second `POST /v1/responses` request with `previous_response_id` plus a `function_call_output` item.
13. The relay exposes `POST /api/v1/chat` which internally performs relay-side orchestration: 1st Responses turn → tool call detection → deep_research execution → 2nd Responses turn → structured `ChatResponse`. The relay uses `LITELLM_CHAT_MODEL` (default `gpt-4o`) for orchestration turns and `LITELLM_MODEL` for deep research.
14. The relay `ChatOrchestrator` uses separate timeouts: `RELAY_TIMEOUT_SECONDS` (default 30 s) for Responses orchestration turns and `RELAY_RESEARCH_TIMEOUT_SECONDS` (default 300 s) for deep_research execution.
15. Upstream errors in auto tool-calling are caught and returned as a structured `ChatResponse` (not bare HTTP 500), and the public payload does not include raw upstream exception text.
16. Direct auto tool-calling surfaces the relevant identifiers to callers: final `response_id`, initial `previous_response_id` when a tool was called, `tool_call_id`, relay `invocation_id`, and relay `upstream_response_id`.
17. Direct clients do not forward the upstream `LITELLM_API_KEY` bearer token to relay `POST /api/v1/tool-invocations`; relay tool execution uses a no-auth local relay request path.

## ChatRequest enhanced contract

18. `POST /api/v1/chat` accepts optional `system_prompt` (string | null) forwarded to the deep_research invocation as the Responses API `instructions` field — enabling persona, output language, or format constraints in relay-orchestrated research.
19. `POST /api/v1/chat` accepts optional `deliverable_format` (default: `"markdown_brief"`) used as the fallback when the Chat Completions model does not specify a format in its tool-call arguments.
20. The Java `RelayClient.invokeChat(message, autoToolCall, systemPrompt, deliverableFormat)` 4-argument overload sends both fields when provided; the 2-argument overload defaults to `system_prompt=null` and `deliverable_format="markdown_brief"`.

## Tests and coverage

21. Automated tests cover: configuration loading, request construction, background handling, status polling, SSE text streaming, error handling, redacted relay error payloads, `system_prompt` passthrough, `text_format` passthrough, `web_search_preview` passthrough, `auto_tool_call` (no-tool and tool-call paths), standard Responses API `function_call_output` continuation, no-auth relay execution for direct auto-tool-calling, `ChatOrchestrator` timeout separation, Pydantic tool_call normalisation, and `ChatRequest.system_prompt` / `ChatRequest.deliverable_format` propagation to `DeepResearchArguments`.
22. Python relay: `uv run pytest --cov=litellm_relay --cov-fail-under=100` passes.
23. Python client: `uv run pytest --cov=litellm_example --cov-fail-under=100` passes.
24. Java: `mvn test` → BUILD SUCCESS.

## Documentation

25. Korean user-facing manuals cover: all CLI flags (`--api`, `--background`, `--web-search`, `--auto-tool-call`, `--timeout`, `--target`, `--stream`, `--deliverable-format`), relay API contract, auto tool-calling guide, system_prompt guide, text_format guide, timeout configuration, key handling, and live verification results.
26. `python-example.md`, `java-example.md`, `quickstart.md`, `responses-guide.md`, `faq.md`, and `relay-example.md` accurately reflect the current feature set.
27. `docs/engineering/acceptance-criteria.md` (this file) is current.
28. The docs site builds successfully with `mkdocs build --strict`.

## Live verification

29. If live credentials are available, at minimum the following are verified before declaring work complete:
    - Python `chat` and `responses` foreground (direct)
    - Python `responses --background` submission (direct)
    - Java `chat` and `responses` foreground (direct)
    - Java `responses --background` submission (direct)
    - Relay foreground tool-invocation
    - Relay background submission
    - Relay `--auto-tool-call` / `/api/v1/chat` with tool-calling topic (tool_called=true)
    - Relay `/api/v1/chat` with non-research topic (tool_called=false)
    - Python `--web-search` (web search result returned)
    - Python `--auto-tool-call` with Responses API function-calling path and returned IDs (`response_id`, `tool_call_id`, `invocation_id`, `upstream_response_id`)
    - Java `--auto-tool-call` with Responses API function-calling path and returned IDs (`response_id`, `tool_call_id`, `invocation_id`, `upstream_response_id`)
    - Relay `/api/v1/chat` with `system_prompt` (persona applied to deep_research result)
    - Relay `/api/v1/chat` with `deliverable_format="markdown_report"` (format used as fallback)
