# Relay Error Redaction Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Stop the relay from exposing raw upstream exception text in public chat and SSE responses while preserving structured failure signaling.

**Architecture:** Tighten the relay's public error contract at the boundary where upstream failures are translated into `ChatResponse` and streamed `ToolInvocationEvent` payloads. Keep internal failure state, but replace caller-visible text with deterministic safe messages aligned to the repository security checklist.

**Tech Stack:** Python 3.12, FastAPI, pytest, LiteLLM relay example

---

### Task 1: Lock down the chat endpoint contract with a failing test

**Files:**
- Modify: `relay/tests/test_chat_orchestrator.py`
- Modify: `relay/src/litellm_relay/chat_orchestrator.py`

**Step 1: Write the failing test**

Update `test_chat_deep_research_error_returns_structured_response` so it asserts the response still reports a tool failure but does not include the raw upstream exception text.

**Step 2: Run test to verify it fails**

Run: `uv run pytest relay/tests/test_chat_orchestrator.py -k deep_research_error_returns_structured_response`
Expected: FAIL because the current response contains the upstream exception text.

**Step 3: Write minimal implementation**

Return a fixed safe public message from `ChatOrchestrator.chat()` when `deep_research` raises.

**Step 4: Run test to verify it passes**

Run: `uv run pytest relay/tests/test_chat_orchestrator.py -k deep_research_error_returns_structured_response`
Expected: PASS

### Task 2: Lock down stream failure exposure with a failing test

**Files:**
- Modify: `relay/tests/test_lifecycle.py`
- Modify: `relay/src/litellm_relay/service.py`

**Step 1: Write the failing test**

Update `test_to_view_includes_error_message_when_stream_fails` so it asserts the stored error remains populated but the public value does not leak the raw exception string.

**Step 2: Run test to verify it fails**

Run: `uv run pytest relay/tests/test_lifecycle.py -k error_message_when_stream_fails`
Expected: FAIL because the current service stores and returns the raw stream exception text.

**Step 3: Write minimal implementation**

Replace the public `error_message` assigned during stream failure handling with a fixed safe message and keep the SSE error event aligned to that value.

**Step 4: Run test to verify it passes**

Run: `uv run pytest relay/tests/test_lifecycle.py -k error_message_when_stream_fails`
Expected: PASS

### Task 3: Update canonical docs and verify repo health

**Files:**
- Modify: `ARCHITECTURE.md`
- Modify: `docs/security/api-security-checklist.md`

**Step 1: Document the public error contract**

Record that relay auto-tool-calling and streaming return safe redacted failure messages to callers.

**Step 2: Run focused and full verification**

Run:
- `cd relay && uv run pytest tests/test_chat_orchestrator.py tests/test_lifecycle.py`
- `cd relay && uv run pytest --cov=litellm_relay --cov-fail-under=100 --cov-report=term-missing`
- `cd clients/python && uv run pytest --cov=litellm_example --cov-fail-under=100 --cov-report=term-missing`
- `cd clients/java && mvn test`
- `mkdocs build --strict`

Expected: all commands succeed.
