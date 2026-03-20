# Responses API Auto Tool Calling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Migrate all auto tool-calling flows in this repository from Chat Completions tool calls to the OpenAI-compatible Responses API function calling pattern.

**Architecture:** Keep the public CLI flags and relay `/api/v1/chat` contract stable while replacing the internal orchestration flow with `responses` first-turn detection plus `previous_response_id`/`function_call_output` continuation. Direct clients should execute the requested tool via relay `tool-invocations` so structured arguments survive unchanged.

**Tech Stack:** Python 3.12+, FastAPI, LiteLLM SDK, Java 21, pytest, JUnit, MkDocs

---

### Task 1: Write failing relay tests for Responses-based orchestration

**Files:**
- Modify: `relay/tests/test_chat_orchestrator.py`
- Modify: `relay/src/litellm_relay/chat_orchestrator.py`

**Step 1: Write the failing test**

Add tests that assert:
- first call uses `litellm.responses()` with a Responses-style tool definition,
- function calls are read from `output[]` items with `type == "function_call"`,
- second call uses `previous_response_id` and `input=[{"type":"function_call_output",...}]`,
- malformed function-call arguments fall back safely,
- first/second-turn failures return redacted `ChatResponse`.

**Step 2: Run test to verify it fails**

Run: `uv run pytest relay/tests/test_chat_orchestrator.py -k "responses or function_call_output or malformed"`
Expected: FAIL because the orchestrator still uses Chat Completions payloads.

**Step 3: Write minimal implementation**

Replace the Chat Completions orchestration path in `ChatOrchestrator` with a Responses API helper flow.

**Step 4: Run test to verify it passes**

Run: `uv run pytest relay/tests/test_chat_orchestrator.py -k "responses or function_call_output or malformed"`
Expected: PASS

### Task 2: Write failing Python direct-client tests for Responses auto tool calling

**Files:**
- Modify: `clients/python/tests/test_client.py`
- Modify: `clients/python/tests/test_main.py`
- Modify: `clients/python/src/litellm_example/client.py`

**Step 1: Write the failing test**

Add tests that assert:
- `create_chat_with_tool_calling()` calls `/v1/responses`, not `/v1/chat/completions`,
- it parses `output[].type == "function_call"`,
- it submits relay execution to `/api/v1/tool-invocations` with preserved `deliverable_format`,
- it continues with `previous_response_id` plus `function_call_output`,
- CLI `--auto-tool-call` still prints the final answer and stderr marker.

**Step 2: Run test to verify it fails**

Run: `uv run pytest clients/python/tests/test_client.py -k auto_tool && uv run pytest clients/python/tests/test_main.py -k auto_tool`
Expected: FAIL because the client still uses Chat Completions and relay `/api/v1/chat`.

**Step 3: Write minimal implementation**

Migrate the Python client flow to Responses API orchestration and relay tool-invocation execution.

**Step 4: Run test to verify it passes**

Run: `uv run pytest clients/python/tests/test_client.py -k auto_tool && uv run pytest clients/python/tests/test_main.py -k auto_tool`
Expected: PASS

### Task 3: Write failing Java tests for Responses auto tool calling

**Files:**
- Modify: `clients/java/src/test/java/example/litellm/LiteLlmClientTest.java`
- Modify: `clients/java/src/test/java/example/litellm/MainTest.java`
- Modify: `clients/java/src/main/java/example/litellm/LiteLlmClient.java`

**Step 1: Write the failing test**

Add tests that assert:
- the Java client uses `/v1/responses` for both turns,
- it parses `function_call` items from `output`,
- it sends `function_call_output` plus `previous_response_id`,
- it executes relay tool calls through `/api/v1/tool-invocations` with preserved arguments,
- CLI behavior remains stable.

**Step 2: Run test to verify it fails**

Run: `mvn -q -Dtest=LiteLlmClientTest,MainTest test`
Expected: FAIL because Java still uses Chat Completions tool calls.

**Step 3: Write minimal implementation**

Mirror the Python migration in `LiteLlmClient.java`.

**Step 4: Run test to verify it passes**

Run: `mvn -q -Dtest=LiteLlmClientTest,MainTest test`
Expected: PASS

### Task 4: Update canonical docs to match the migrated contract

**Files:**
- Modify: `docs/engineering/acceptance-criteria.md`
- Modify: `ARCHITECTURE.md`
- Modify: `docs/ko/auto-toolcalling.md`
- Modify: `docs/ko/relay-example.md`
- Modify: `docs/ko/python-example.md`
- Modify: `docs/ko/java-example.md`
- Modify: `docs/ko/responses-guide.md`
- Modify: `docs/ko/quickstart.md`
- Modify: `docs/ko/faq.md`
- Modify: `docs/ko/manual.md`

**Step 1: Update docs**

Replace Chat Completions-based auto tool-calling explanations with Responses API `function_call` / `function_call_output` flow, and record that direct clients execute the tool via relay `tool-invocations`.

**Step 2: Run docs build**

Run: `mkdocs build --strict`
Expected: PASS

### Task 5: Run full verification

**Files:**
- Verify only

**Step 1: Run focused relay verification**

Run: `cd relay && uv run pytest tests/test_chat_orchestrator.py tests/test_app.py tests/test_upstream.py`
Expected: PASS

**Step 2: Run full relay suite**

Run: `cd relay && uv run pytest --cov=litellm_relay --cov-fail-under=100 --cov-report=term-missing`
Expected: PASS

**Step 3: Run Python client suite**

Run: `cd clients/python && uv run pytest --cov=litellm_example --cov-fail-under=100 --cov-report=term-missing`
Expected: PASS

**Step 4: Run Java suite**

Run: `cd clients/java && mvn test`
Expected: PASS

**Step 5: Run docs build**

Run: `mkdocs build --strict`
Expected: PASS
