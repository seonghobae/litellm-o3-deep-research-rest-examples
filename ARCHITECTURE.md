# Architecture

This repository is intentionally small and split by language under `clients/`.

## Structure
- `clients/python/`: Python example package, CLI entrypoint, and pytest suite.
- `clients/java/`: Java 21 example application, Maven build, and JUnit suite for both direct LiteLLM calls and relay-calling mode.
- `relay/`: FastAPI + Hypercorn relay example backed by the LiteLLM Python SDK.
- `docs/`: repository-specific contributor guidance, acceptance criteria, workflow notes, and Korean user-facing manuals.
- `.github/workflows/`: CI that verifies both direct clients, the relay example, and the docs site build.
- `mkdocs.yml`: GitHub Pages publication entrypoint for the Korean docs site.

## Design choices
- Both clients support the OpenAI-compatible `POST /v1/chat/completions` and `POST /v1/responses` endpoints.
- Both clients also support submitting `POST /v1/responses` requests with `background: true` so LiteLLM can enqueue server-side background work while the local CLI remains a foreground one-shot process.
- Both clients accept `LITELLM_BASE_URL` as either the proxy root or `/v1`, and normalise it to a predictable `/v1/` API base.
- Both clients load `LITELLM_API_KEY` and `LITELLM_BASE_URL` from the process environment, with `~/.env` as an optional fallback for local development.
- Foreground `responses` calls extract text output for convenience, while background `responses` calls return raw JSON metadata so callers can inspect response identifiers and status.
- The relay example uses the LiteLLM Python SDK against the upstream LiteLLM Proxy, but it keeps that internal by exposing `POST /api/v1/tool-invocations` plus status/wait/events resources.
- The relay maps structured deep-research arguments to an internal LiteLLM Responses request and uses Hypercorn as the ASGI runtime.
- The Java example now has a separate relay mode that targets `RELAY_BASE_URL` instead of the upstream LiteLLM Proxy directly.
- A Korean GitHub Pages documentation site is built from `docs/` with MkDocs Material.
- Streaming and tool-calling remain intentionally out of scope for the direct Python client, but they are implemented in the relay example as a text-focused SSE flow.
- **Auto tool-calling** (`POST /api/v1/chat`): the relay also exposes a chat endpoint where the model autonomously decides whether to invoke `deep_research` via function calling.  The orchestrator uses two separate timeouts: `RELAY_TIMEOUT_SECONDS` (default 30 s) for Chat Completions turns and `RELAY_RESEARCH_TIMEOUT_SECONDS` (default 300 s) for the deep research invocation.  Upstream errors are surfaced as structured `ChatResponse` payloads rather than bare HTTP 500s.
- **web_search_preview**: both Python and Java direct clients support `tools=[{"type":"web_search_preview"}]` via the `--web-search` CLI flag.
- **system_prompt** maps to the Responses API `instructions` field so relay callers can inject personas and output constraints without polluting the research question.
- **text_format** maps to the Responses API `text.format` field for machine-readable JSON output (`json_object` / `json_schema`).  Supported by gpt-4o; `json_schema` is rejected by o3-deep-research at the API level.
