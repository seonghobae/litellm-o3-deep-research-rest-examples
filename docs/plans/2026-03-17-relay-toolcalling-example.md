# Relay Tool-Calling Example Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a third example to this repository: a FastAPI + Hypercorn relay that wraps the LiteLLM Python SDK against an upstream LiteLLM Proxy and exposes a structured, tool-calling-like contract for Java callers instead of a raw `input` field passthrough.

**Architecture:** Keep the existing direct Python and Java examples intact, and add a separate relay example under a new top-level `relay/` package. The relay owns request validation, request-to-LiteLLM translation, background/polling/stream lifecycle handling, and a small Java caller mode that targets the relay contract rather than the upstream proxy directly.

**Tech Stack:** FastAPI, Hypercorn, LiteLLM Python SDK, Pydantic, uv, pytest, Java 21, Maven, JDK HttpClient.

---

## Repository facts and canonical task selection

- Current repo state: direct Python and Java examples already support `chat/completions`, `responses`, `background: true`, and have green CI on `main`.
- Current GitHub state: no open issues, no open PRs, no milestones, no project items, default labels only.
- Current canonical gap at task selection time: there was no repository-local implementation plan for the user-requested third example (relay example), and there is still no relay package implemented yet.
- Canonical task selected: **produce a repository-local implementation plan for the relay example, grounded in the current repo structure and constraints.**

## Target end state

After this plan is implemented in a later execution session, the repository should contain three examples:

1. `clients/python/` — direct Python caller example
2. `clients/java/` — direct Java caller example, optionally extended with relay-calling mode
3. `relay/` — FastAPI + Hypercorn relay example using LiteLLM Python SDK against the upstream LiteLLM Proxy

The relay should present a **tool invocation contract**, not a generic free-form `input` passthrough. The Java side should call the relay using structured arguments such as `research_question`, `constraints`, and `deliverable_format`, which the relay translates to the upstream LiteLLM SDK call.

---

### Task 1: Scaffold the relay package and shared configuration

**Files:**
- Create: `relay/pyproject.toml`
- Create: `relay/README.md`
- Create: `relay/src/litellm_relay/__init__.py`
- Create: `relay/src/litellm_relay/config.py`
- Create: `relay/src/litellm_relay/__main__.py`
- Create: `relay/tests/test_config.py`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `AGENTS.md`

**Step 1: Write the failing config and startup tests**

```python
def test_loads_relay_settings_from_env_and_dotenv(tmp_path, monkeypatch):
    ...

def test_main_builds_hypercorn_bind_from_settings(monkeypatch):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd relay && uv run pytest tests/test_config.py -v`
Expected: FAIL because the relay package and config objects do not exist yet.

**Step 3: Write minimal implementation**

Create a `RelaySettings` model that loads:

- `LITELLM_BASE_URL`
- `LITELLM_API_KEY`
- `LITELLM_MODEL` (default `o3-deep-research`)
- `RELAY_HOST` (default `127.0.0.1`)
- `RELAY_PORT` (default `8080`)
- `RELAY_TIMEOUT_SECONDS` (default `30`)

The relay must follow the same repository configuration policy as the existing
Python example:

- read real environment variables first
- optionally load `~/.env` as a local-development fallback
- do **not** silently read a project-local `.env`

Create a thin `__main__.py` that starts Hypercorn with:

```python
from hypercorn.asyncio import serve
from hypercorn.config import Config
```

**Step 4: Run tests to verify they pass**

Run: `cd relay && uv run pytest tests/test_config.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add relay/pyproject.toml relay/src/litellm_relay relay/README.md README.md ARCHITECTURE.md AGENTS.md
git commit -m "feat: scaffold LiteLLM relay example"
```

---

### Task 2: Define the tool-calling-like relay contract

**Files:**
- Create: `relay/src/litellm_relay/contracts.py`
- Create: `relay/tests/test_contracts.py`
- Modify: `relay/README.md`

**Step 1: Write the failing contract tests**

```python
def test_tool_invocation_request_requires_tool_name_and_arguments():
    payload = {
        "tool_name": "deep_research",
        "arguments": {
            "research_question": "What changed in Azure OpenAI o3-deep-research?",
            "deliverable_format": "markdown_brief",
        },
    }
    model = ToolInvocationRequest.model_validate(payload)
    assert model.tool_name == "deep_research"

def test_unknown_tool_name_is_rejected():
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd relay && uv run pytest tests/test_contracts.py -v`
Expected: FAIL because the request/response contract types do not exist yet.

**Step 3: Write minimal implementation**

Define Pydantic models such as:

```python
class DeepResearchArguments(BaseModel):
    research_question: str
    context: list[str] = []
    constraints: list[str] = []
    deliverable_format: Literal["markdown_brief", "markdown_report", "json_outline"]
    require_citations: bool = True
    background: bool = False
    stream: bool = False

class ToolInvocationRequest(BaseModel):
    tool_name: Literal["deep_research"]
    arguments: DeepResearchArguments
```

Return models should separate:

- synchronous completed text output
- queued/background metadata
- stream/event mode metadata

**Step 4: Run tests to verify they pass**

Run: `cd relay && uv run pytest tests/test_contracts.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add relay/src/litellm_relay/contracts.py relay/tests/test_contracts.py relay/README.md
git commit -m "feat: define relay tool invocation contract"
```

---

### Task 3: Add the LiteLLM SDK adapter layer

**Files:**
- Create: `relay/src/litellm_relay/upstream.py`
- Create: `relay/tests/test_upstream.py`

**Step 1: Write the failing adapter tests**

```python
def test_builds_foreground_responses_request_from_tool_arguments(monkeypatch):
    ...

def test_builds_background_responses_request(monkeypatch):
    ...

def test_builds_streaming_responses_request(monkeypatch):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd relay && uv run pytest tests/test_upstream.py -v`
Expected: FAIL because there is no adapter translating tool arguments to LiteLLM SDK requests.

**Step 3: Write minimal implementation**

Implement a gateway class, for example:

```python
class LiteLLMRelayGateway:
    async def invoke_deep_research(self, args: DeepResearchArguments) -> UpstreamResult:
        ...

    async def get_response(self, response_id: str) -> dict:
        ...
```

Use the LiteLLM Python SDK with a configured `base_url` and `api_key` that point to the upstream LiteLLM Proxy.

Important mapping rule:

- The relay API accepts `tool_name` + structured `arguments`
- The adapter converts that into the upstream LiteLLM SDK call
- The upstream request may still use `input`, but **that detail stays inside the relay**, not in the public relay contract

**Step 4: Run tests to verify they pass**

Run: `cd relay && uv run pytest tests/test_upstream.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add relay/src/litellm_relay/upstream.py relay/tests/test_upstream.py
git commit -m "feat: add LiteLLM SDK relay gateway"
```

---

### Task 4: Add the FastAPI application and endpoints

**Files:**
- Create: `relay/src/litellm_relay/app.py`
- Create: `relay/src/litellm_relay/service.py`
- Create: `relay/tests/test_app.py`

**Step 1: Write the failing API tests**

```python
def test_post_tool_invocations_returns_completed_result(client):
    ...

def test_post_tool_invocations_returns_background_metadata(client):
    ...

def test_get_tool_invocations_by_id_returns_latest_status(client):
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd relay && uv run pytest tests/test_app.py -v`
Expected: FAIL because the FastAPI app and handlers do not exist.

**Step 3: Write minimal implementation**

Use REST-style resource endpoints:

- `POST /api/v1/tool-invocations`
- `GET /api/v1/tool-invocations/{invocation_id}`
- `GET /api/v1/tool-invocations/{invocation_id}/wait`
- `GET /api/v1/tool-invocations/{invocation_id}/events`

Recommended POST body for Java callers:

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "Summarize Azure OpenAI o3-deep-research relay patterns.",
    "context": ["Azure Landing Zone", "LiteLLM Proxy"],
    "constraints": ["Use markdown output", "Call out security assumptions"],
    "deliverable_format": "markdown_brief",
    "require_citations": true,
    "background": true,
    "stream": false
  }
}
```

Behavior:

- foreground → return completed text result
- background → return relay invocation id + upstream response id + status metadata
- wait endpoint → block/poll until completion and return final text
- events endpoint → expose SSE for stream mode or polled status events

**Step 4: Run tests to verify they pass**

Run: `cd relay && uv run pytest tests/test_app.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add relay/src/litellm_relay/app.py relay/src/litellm_relay/service.py relay/tests/test_app.py
git commit -m "feat: add FastAPI relay endpoints"
```

---

### Task 5: Add polling, retrieval, and streaming lifecycle handling

**Files:**
- Create: `relay/tests/test_lifecycle.py`
- Modify: `relay/src/litellm_relay/service.py`
- Modify: `relay/src/litellm_relay/upstream.py`

**Step 1: Write the failing lifecycle tests**

```python
def test_wait_endpoint_polls_upstream_until_completed():
    ...

def test_events_endpoint_relays_text_deltas_as_sse():
    ...
```

**Step 2: Run tests to verify they fail**

Run: `cd relay && uv run pytest tests/test_lifecycle.py -v`
Expected: FAIL until lifecycle behavior exists.

**Step 3: Write minimal implementation**

Implement:

- upstream response-id retrieval via LiteLLM SDK or compatible GET path
- timeout-bounded polling for background jobs
- text-only SSE relay for stream mode

Keep the relay simple:

- ignore non-text tool stream events in the first pass
- keep response metadata intact
- redact secrets from all logs and errors

**Step 4: Run tests to verify they pass**

Run: `cd relay && uv run pytest tests/test_lifecycle.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add relay/src/litellm_relay/service.py relay/src/litellm_relay/upstream.py relay/tests/test_lifecycle.py
git commit -m "feat: add relay lifecycle support"
```

---

### Task 6: Extend the Java example with a relay caller mode

**Files:**
- Modify: `clients/java/src/main/java/example/litellm/Main.java`
- Create: `clients/java/src/main/java/example/litellm/relay/RelayClient.java`
- Create: `clients/java/src/test/java/example/litellm/RelayClientTest.java`
- Modify: `clients/java/README.md`

**Step 1: Write the failing Java relay tests**

```java
@Test
void posts_tool_invocation_request_to_relay() { ... }

@Test
void reads_completed_text_from_relay_wait_endpoint() { ... }
```

**Step 2: Run tests to verify they fail**

Run: `cd clients/java && mvn -Dtest=RelayClientTest test`
Expected: FAIL because the relay caller does not exist.

**Step 3: Write minimal implementation**

Add a Java relay caller mode that sends structured JSON to the relay instead of direct LiteLLM calls.

Recommended request shape:

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "...",
    "deliverable_format": "markdown_brief",
    "background": false,
    "stream": false
  }
}
```

Keep direct proxy mode and relay mode separate so the existing Java example remains valid.

**Step 4: Run tests to verify they pass**

Run: `cd clients/java && mvn -Dtest=RelayClientTest test`
Expected: PASS.

**Step 5: Commit**

```bash
git add clients/java/src/main/java/example/litellm/relay/RelayClient.java clients/java/src/test/java/example/litellm/RelayClientTest.java clients/java/src/main/java/example/litellm/Main.java clients/java/README.md
git commit -m "feat: add Java relay caller example"
```

---

### Task 7: Update canonical docs and end-to-end verification

**Files:**
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `ARCHITECTURE.md`
- Modify: `AGENTS.md`
- Modify: `docs/engineering/acceptance-criteria.md`
- Modify: `docs/engineering/harness-engineering.md`
- Modify: `docs/ko/manual.md`
- Modify: `docs/workflow/one-day-delivery-plan.md`

**Step 1: Write the failing verification checklist**

Create a checklist in the docs update commit description covering:

- direct Python example still works
- direct Java example still works
- relay example is covered by CI
- relay example starts under Hypercorn
- Java can call relay in sync/background/stream modes

**Step 2: Run the full verification commands**

Run:

```bash
cd /path/to/repo/relay && uv run pytest
cd /path/to/repo/clients/python && uv run pytest
cd /path/to/repo/clients/java && mvn test
```

Live verification commands:

```bash
cd /path/to/repo/relay && uv run python -m litellm_relay
cd /path/to/repo/clients/python && uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
cd /path/to/repo/clients/java && mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

Additional relay verification (once implemented):

```bash
curl -X POST http://127.0.0.1:8080/api/v1/tool-invocations \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "deep_research",
    "arguments": {
      "research_question": "Summarize relay architecture.",
      "deliverable_format": "markdown_brief",
      "background": false,
      "stream": false
    }
  }'
```

**Step 3: Commit docs and verification updates**

```bash
git add .github/workflows/ci.yml README.md ARCHITECTURE.md AGENTS.md docs/engineering/acceptance-criteria.md docs/engineering/harness-engineering.md docs/ko/manual.md docs/workflow/one-day-delivery-plan.md relay/README.md clients/java/README.md
git commit -m "docs: describe relay tool-calling example"
```

---

## Risks and assumptions

1. The upstream LiteLLM Proxy may support `responses`, `background`, and streaming differently depending on the Azure OpenAI deployment configuration.
2. The relay should hide raw upstream `input` usage from Java callers, but it still needs an internal mapping layer that converts structured tool arguments into LiteLLM SDK requests.
3. Streaming should remain text-focused in the first version; avoid overengineering full event taxonomies.
4. Hypercorn is the chosen ASGI server for the relay example and should be added to repository docs as an explicit relay design choice when implementation starts.
5. The relay example should remain a minimal example, not a production orchestration platform.

## Suggested future relay API contract

### Create invocation

`POST /api/v1/tool-invocations`

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "What does the relay add over direct LiteLLM calls?",
    "context": ["Azure OpenAI", "LiteLLM Proxy", "FastAPI relay"],
    "constraints": ["Return markdown", "Mention security boundaries"],
    "deliverable_format": "markdown_brief",
    "require_citations": true,
    "background": true,
    "stream": false
  }
}
```

### Retrieve invocation metadata

`GET /api/v1/tool-invocations/{invocation_id}`

### Wait for final result

`GET /api/v1/tool-invocations/{invocation_id}/wait`

### Stream events

`GET /api/v1/tool-invocations/{invocation_id}/events`

This keeps the public relay contract resource-oriented while still modeling a “tool invocation” abstraction for Java callers.
