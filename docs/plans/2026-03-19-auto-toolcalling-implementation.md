# Auto Tool-Calling Deep Research Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** (1) Fix existing bugs (manual numbering, GitHub Pages CI deploy), (2) implement "일반 대화 중 deep_research 자동 개입" — client-side function calling (Python + Java) and relay-side orchestration (`POST /api/v1/chat`), (3) test, evaluate, and document everything including GitHub Pages update.

**Architecture:** Two layers of auto tool-calling are added in parallel. Layer A: Python and Java clients gain `--auto-tool-call` CLI flag using Chat Completions function calling → relay invocation → 2nd completions turn. Layer C: relay gets `POST /api/v1/chat` that does full orchestration server-side so callers only need a single chat message. Both layers use gpt-4o as the orchestrating LLM and the existing relay `deep_research` tool for actual research. All tests are pure mocks; no live API required.

**Tech Stack:** Python/uv, FastAPI, Pydantic, pytest, asyncio, Java 21/Maven, Jackson, JDK HttpClient, MkDocs Material.

---

## Pre-conditions

- Working directory: `/Users/seonghobae/opencode_tasks/litellm-o3-deep-research-rest-examples`
- Latest commit: `3fa76ba` on `main`, all CI green
- relay 59 tests, python 100% coverage, java BUILD SUCCESS

---

## Task 0: Fix section numbering bug in docs/ko/manual.md

**Files:**
- Modify: `docs/ko/manual.md` (lines 705–775 — the "9-1" through "9-7" sub-section numbering in section 11)

**Step 1: Apply the fix**

In `docs/ko/manual.md`, change all occurrences of `### 9-1.`, `### 9-2.`, ..., `### 9-7.` that appear *inside section 11* (after line 700) to `### 11-1.`, `### 11-2.`, ..., `### 11-7.`.

Also fix the section 12 heading to not conflict: it should remain `## 12. 요약`.

**Step 2: Verify mkdocs still builds**

```bash
cd /Users/seonghobae/opencode_tasks/litellm-o3-deep-research-rest-examples
pip install -r requirements-docs.txt -q
mkdocs build --strict
```

Expected: `INFO - Documentation built!` with no warnings about duplicate anchors.

**Step 3: Commit**

```bash
git add docs/ko/manual.md
git commit -m "fix: correct section numbering in manual (11-1~11-7 not 9-1~9-7)"
```

---

## Task 1: Add GitHub Pages deploy to CI

**Files:**
- Modify: `.github/workflows/ci.yml`

**Step 1: Add gh-deploy step to the docs job**

In `.github/workflows/ci.yml`, after `run: mkdocs build --strict`, add:

```yaml
      - name: Deploy to GitHub Pages
        if: github.ref == 'refs/heads/main' && github.event_name == 'push'
        run: mkdocs gh-deploy --force
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
```

Also add `fetch-depth: 0` to the checkout step so git history is available for `gh-deploy`:

```yaml
      - uses: actions/checkout@93cb6efe18208431cddfb8368fd83d5badbf9bfd # v5
        with:
          fetch-depth: 0
```

**Step 2: Verify the workflow file is valid YAML**

```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" && echo "YAML OK"
```

Expected: `YAML OK`

**Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: deploy GitHub Pages on push to main"
```

---

## Task 2: Add relay contracts for Chat endpoint

**Files:**
- Modify: `relay/src/litellm_relay/contracts.py`
- Modify: `relay/tests/test_contracts.py`

**Step 1: Write the failing contract tests**

Add to `relay/tests/test_contracts.py`:

```python
from litellm_relay.contracts import ChatRequest, ChatResponse


def test_chat_request_defaults():
    req = ChatRequest(message="Hello")
    assert req.message == "Hello"
    assert req.context == []
    assert req.auto_tool_call is True


def test_chat_request_with_context():
    req = ChatRequest(message="Q", context=["ctx1"], auto_tool_call=False)
    assert req.context == ["ctx1"]
    assert req.auto_tool_call is False


def test_chat_response_tool_called():
    resp = ChatResponse(
        content="answer",
        tool_called=True,
        tool_name="deep_research",
        research_summary="summary",
    )
    assert resp.tool_called is True
    assert resp.tool_name == "deep_research"


def test_chat_response_no_tool():
    resp = ChatResponse(content="hi", tool_called=False)
    assert resp.tool_name is None
    assert resp.research_summary is None
```

Run: `cd relay && uv run pytest tests/test_contracts.py -v`
Expected: FAIL (ImportError — ChatRequest not defined)

**Step 2: Add the models to contracts.py**

Add to the bottom of `relay/src/litellm_relay/contracts.py`:

```python
class ChatRequest(BaseModel):
    """Inbound payload for ``POST /api/v1/chat``.

    The relay uses the ``message`` as the user turn in a Chat Completions
    request with a ``deep_research`` function tool attached.  When the model
    decides the question warrants deep research it returns a tool call; the
    relay executes the research and performs a second completions turn to
    produce the final natural-language answer.
    """

    message: str
    context: list[str] = Field(default_factory=list)
    auto_tool_call: bool = True


class ChatResponse(BaseModel):
    """Outbound payload for ``POST /api/v1/chat``."""

    content: str
    tool_called: bool
    tool_name: str | None = None
    research_summary: str | None = None
```

**Step 3: Run the tests**

```bash
cd relay && uv run pytest tests/test_contracts.py -v
```

Expected: PASS for all new tests plus all existing contract tests.

**Step 4: Commit**

```bash
git add relay/src/litellm_relay/contracts.py relay/tests/test_contracts.py
git commit -m "feat: add ChatRequest/ChatResponse contracts for /api/v1/chat"
```

---

## Task 3: Implement relay-side chat orchestrator

**Files:**
- Create: `relay/src/litellm_relay/chat_orchestrator.py`
- Create: `relay/tests/test_chat_orchestrator.py`

**Step 1: Write failing tests**

Create `relay/tests/test_chat_orchestrator.py`:

```python
from __future__ import annotations

import pytest

from litellm_relay.contracts import ChatRequest
from litellm_relay.chat_orchestrator import ChatOrchestrator


DEEP_RESEARCH_TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "deep_research",
        "description": "Conduct in-depth research on a topic.",
        "parameters": {
            "type": "object",
            "properties": {
                "research_question": {"type": "string"},
                "deliverable_format": {
                    "type": "string",
                    "enum": ["markdown_brief", "markdown_report", "json_outline"],
                },
            },
            "required": ["research_question", "deliverable_format"],
        },
    },
}


@pytest.mark.asyncio
async def test_chat_no_tool_call_returns_direct_answer(monkeypatch):
    """When the model does not call deep_research, return the assistant text directly."""
    calls = []

    def fake_completions(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "Hello there!", "tool_calls": None},
                }
            ]
        }

    monkeypatch.setattr("litellm_relay.chat_orchestrator.litellm.completion", fake_completions)

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )
    result = await orchestrator.chat(ChatRequest(message="Hello", auto_tool_call=True))

    assert result.content == "Hello there!"
    assert result.tool_called is False
    assert result.tool_name is None
    assert len(calls) == 1  # only one turn


@pytest.mark.asyncio
async def test_chat_with_tool_call_executes_deep_research(monkeypatch):
    """When the model calls deep_research, orchestrator runs it and completes a second turn."""
    turn = 0

    def fake_completions(**kwargs):
        nonlocal turn
        turn += 1
        if turn == 1:
            # first turn: model decides to call deep_research
            return {
                "choices": [
                    {
                        "finish_reason": "tool_calls",
                        "message": {
                            "role": "assistant",
                            "content": None,
                            "tool_calls": [
                                {
                                    "id": "call_abc",
                                    "type": "function",
                                    "function": {
                                        "name": "deep_research",
                                        "arguments": '{"research_question": "짜장면의 역사", "deliverable_format": "markdown_brief"}',
                                    },
                                }
                            ],
                        },
                    }
                ]
            }
        else:
            # second turn: model synthesises tool result
            return {
                "choices": [
                    {
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": "짜장면은 19세기 말 중국 산둥 지방에서 유래했습니다.",
                            "tool_calls": None,
                        },
                    }
                ]
            }

    async def fake_invoke(args):
        from litellm_relay.upstream import UpstreamInvocationResult
        return UpstreamInvocationResult(
            mode="foreground",
            status="completed",
            output_text="역사 요약: 인천 차이나타운 기원",
        )

    monkeypatch.setattr("litellm_relay.chat_orchestrator.litellm.completion", fake_completions)

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )
    # Patch the internal gateway invoke
    orchestrator._invoke_deep_research = fake_invoke

    result = await orchestrator.chat(ChatRequest(message="짜장면의 역사를 자세히 알려줘"))

    assert result.tool_called is True
    assert result.tool_name == "deep_research"
    assert "짜장면" in result.content
    assert result.research_summary == "역사 요약: 인천 차이나타운 기원"
    assert turn == 2  # two completions turns


@pytest.mark.asyncio
async def test_chat_auto_tool_call_false_skips_tools(monkeypatch):
    """When auto_tool_call=False, the orchestrator does not attach tools."""
    calls = []

    def fake_completions(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "No tools used.", "tool_calls": None},
                }
            ]
        }

    monkeypatch.setattr("litellm_relay.chat_orchestrator.litellm.completion", fake_completions)

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )
    result = await orchestrator.chat(ChatRequest(message="안녕", auto_tool_call=False))

    assert result.content == "No tools used."
    assert result.tool_called is False
    # tools kwarg should not be present when auto_tool_call=False
    assert "tools" not in calls[0]


@pytest.mark.asyncio
async def test_chat_with_context_includes_context_in_first_turn(monkeypatch):
    """Context items are prepended to the user message."""
    calls = []

    def fake_completions(**kwargs):
        calls.append(kwargs)
        return {
            "choices": [
                {
                    "finish_reason": "stop",
                    "message": {"role": "assistant", "content": "got it", "tool_calls": None},
                }
            ]
        }

    monkeypatch.setattr("litellm_relay.chat_orchestrator.litellm.completion", fake_completions)

    orchestrator = ChatOrchestrator(
        base_url="https://proxy.example/v1",
        api_key="sk-test",
        chat_model="litellm_proxy/gpt-4o",
        timeout_seconds=10.0,
    )
    await orchestrator.chat(ChatRequest(message="Q", context=["ctx A", "ctx B"]))

    messages = calls[0]["messages"]
    user_content = next(m["content"] for m in messages if m["role"] == "user")
    assert "ctx A" in user_content
    assert "ctx B" in user_content
    assert "Q" in user_content
```

Run: `cd relay && uv run pytest tests/test_chat_orchestrator.py -v`
Expected: FAIL (ImportError)

**Step 2: Implement the orchestrator**

Create `relay/src/litellm_relay/chat_orchestrator.py`:

```python
from __future__ import annotations

import asyncio
import json
from typing import Any

import litellm

from .contracts import ChatRequest, ChatResponse, DeepResearchArguments
from .upstream import LiteLLMRelayGateway, UpstreamInvocationResult

DEEP_RESEARCH_TOOL_SCHEMA: dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "deep_research",
        "description": (
            "Conduct in-depth research on a topic and return a detailed report. "
            "Use this when the user asks for detailed factual information, history, "
            "analysis, or comprehensive explanations that require research beyond "
            "general knowledge."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "research_question": {
                    "type": "string",
                    "description": "The specific research question or topic to investigate",
                },
                "deliverable_format": {
                    "type": "string",
                    "enum": ["markdown_brief", "markdown_report", "json_outline"],
                    "description": "Format of the research output",
                },
            },
            "required": ["research_question", "deliverable_format"],
        },
    },
}


class ChatOrchestrator:
    """Relay-side orchestration for automatic deep_research tool calling.

    Flow
    ----
    1. Build a Chat Completions request with the ``deep_research`` function
       tool attached.
    2. If the model responds with ``finish_reason == "tool_calls"`` for
       ``deep_research``, execute the research via the upstream relay gateway.
    3. Append the tool result to the conversation and send a second Chat
       Completions request to obtain the final natural-language answer.
    4. Return a :class:`~litellm_relay.contracts.ChatResponse` capturing
       whether a tool was called and, if so, the research summary.
    """

    def __init__(
        self,
        base_url: str,
        api_key: str,
        chat_model: str = "litellm_proxy/gpt-4o",
        research_model: str = "litellm_proxy/o3-deep-research",
        timeout_seconds: float = 30.0,
    ) -> None:
        self._base_url = base_url
        self._api_key = api_key
        self._chat_model = chat_model
        self._research_model = research_model
        self._timeout_seconds = timeout_seconds
        self._gateway = LiteLLMRelayGateway(
            base_url=base_url,
            api_key=api_key,
            model=research_model.removeprefix("litellm_proxy/"),
            timeout_seconds=timeout_seconds,
        )

    async def chat(self, request: ChatRequest) -> ChatResponse:
        """Perform an orchestrated chat turn, optionally invoking deep_research."""
        user_content = self._build_user_content(request)
        messages: list[dict[str, Any]] = [{"role": "user", "content": user_content}]

        kwargs: dict[str, Any] = {
            "model": self._chat_model,
            "messages": messages,
            "api_base": self._base_url,
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
        }
        if request.auto_tool_call:
            kwargs["tools"] = [DEEP_RESEARCH_TOOL_SCHEMA]

        first_response = await asyncio.to_thread(litellm.completion, **kwargs)
        first_choice = self._extract_choice(first_response)
        first_message = first_choice.get("message", {})

        tool_calls = first_message.get("tool_calls") or []
        deep_research_call = next(
            (
                tc
                for tc in tool_calls
                if isinstance(tc, dict)
                and tc.get("type") == "function"
                and (tc.get("function") or {}).get("name") == "deep_research"
            ),
            None,
        )

        if deep_research_call is None:
            # No tool call — return the assistant's direct answer
            content = first_message.get("content") or ""
            return ChatResponse(content=content, tool_called=False)

        # Parse the tool call arguments
        raw_args = (deep_research_call.get("function") or {}).get("arguments", "{}")
        try:
            tool_args = json.loads(raw_args)
        except json.JSONDecodeError:
            tool_args = {}

        research_question = tool_args.get("research_question", request.message)
        deliverable_format = tool_args.get("deliverable_format", "markdown_brief")

        # Execute deep research
        research_result = await self._invoke_deep_research(
            DeepResearchArguments(
                research_question=research_question,
                deliverable_format=deliverable_format,
            )
        )
        research_summary = research_result.output_text or ""

        # Build second turn: append assistant tool call + tool result
        tool_call_id = deep_research_call.get("id", "call_0")
        messages_with_result: list[dict[str, Any]] = [
            {"role": "user", "content": user_content},
            {"role": "assistant", "content": None, "tool_calls": [deep_research_call]},
            {
                "role": "tool",
                "tool_call_id": tool_call_id,
                "content": research_summary,
            },
        ]

        second_kwargs: dict[str, Any] = {
            "model": self._chat_model,
            "messages": messages_with_result,
            "api_base": self._base_url,
            "api_key": self._api_key,
            "timeout": self._timeout_seconds,
        }
        second_response = await asyncio.to_thread(litellm.completion, **second_kwargs)
        second_choice = self._extract_choice(second_response)
        final_content = (second_choice.get("message") or {}).get("content") or ""

        return ChatResponse(
            content=final_content,
            tool_called=True,
            tool_name="deep_research",
            research_summary=research_summary,
        )

    async def _invoke_deep_research(
        self, args: DeepResearchArguments
    ) -> UpstreamInvocationResult:
        return await self._gateway.invoke_deep_research(args)

    @staticmethod
    def _build_user_content(request: ChatRequest) -> str:
        if not request.context:
            return request.message
        context_block = "\n".join(f"- {item}" for item in request.context)
        return f"Context:\n{context_block}\n\n{request.message}"

    @staticmethod
    def _extract_choice(response: Any) -> dict[str, Any]:
        if isinstance(response, dict):
            choices = response.get("choices") or []
        elif hasattr(response, "choices"):
            choices = response.choices or []
        else:
            choices = []
        if not choices:
            return {}
        first = choices[0]
        if isinstance(first, dict):
            return first
        if hasattr(first, "model_dump"):
            result = first.model_dump()
            return result if isinstance(result, dict) else {}
        return {}
```

**Step 3: Run the tests**

```bash
cd relay && uv run pytest tests/test_chat_orchestrator.py -v
```

Expected: PASS for all 4 tests.

**Step 4: Run all relay tests with coverage**

```bash
cd relay && uv run pytest --cov=litellm_relay --cov-fail-under=100 --cov-report=term-missing
```

Expected: PASS, 100% coverage.

**Step 5: Commit**

```bash
git add relay/src/litellm_relay/chat_orchestrator.py relay/tests/test_chat_orchestrator.py relay/src/litellm_relay/contracts.py relay/tests/test_contracts.py
git commit -m "feat: add relay-side chat orchestrator with auto deep_research tool calling"
```

---

## Task 4: Add POST /api/v1/chat endpoint to relay app

**Files:**
- Modify: `relay/src/litellm_relay/app.py`
- Modify: `relay/src/litellm_relay/config.py`
- Modify: `relay/tests/test_app.py`

**Step 1: Write failing tests**

Add to `relay/tests/test_app.py` (insert before existing tests or at the bottom):

```python
from unittest.mock import AsyncMock, patch

from litellm_relay.contracts import ChatRequest, ChatResponse


def test_post_chat_returns_direct_answer(client):
    """POST /api/v1/chat with auto_tool_call=False returns plain assistant answer."""
    with patch(
        "litellm_relay.app.ChatOrchestrator.chat",
        new_callable=AsyncMock,
        return_value=ChatResponse(content="hello", tool_called=False),
    ):
        resp = client.post(
            "/api/v1/chat",
            json={"message": "안녕", "auto_tool_call": False},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["content"] == "hello"
    assert data["tool_called"] is False


def test_post_chat_returns_tool_called_response(client):
    """POST /api/v1/chat that triggers deep_research returns tool metadata."""
    with patch(
        "litellm_relay.app.ChatOrchestrator.chat",
        new_callable=AsyncMock,
        return_value=ChatResponse(
            content="짜장면의 역사는...",
            tool_called=True,
            tool_name="deep_research",
            research_summary="인천 차이나타운 기원",
        ),
    ):
        resp = client.post(
            "/api/v1/chat",
            json={"message": "짜장면의 역사를 알려줘"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["tool_called"] is True
    assert data["tool_name"] == "deep_research"
    assert data["research_summary"] == "인천 차이나타운 기원"
```

Run: `cd relay && uv run pytest tests/test_app.py -v -k "test_post_chat"`
Expected: FAIL (404 — endpoint not defined)

**Step 2: Add the ChatOrchestrator config fields**

In `relay/src/litellm_relay/config.py`, add `chat_model` field to `RelaySettings`:

```python
chat_model: str = Field(
    default="gpt-4o",
    validation_alias=AliasChoices("LITELLM_CHAT_MODEL", "chat_model"),
    description="LiteLLM model name used for chat completions / orchestration turns.",
)
```

Also add a test in `relay/tests/test_config.py`:

```python
def test_chat_model_defaults_to_gpt_4o(monkeypatch):
    monkeypatch.setenv("LITELLM_API_KEY", "sk-x")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://h/v1")
    settings = load_settings(env_file=None)
    assert settings.chat_model == "gpt-4o"


def test_chat_model_can_be_overridden(monkeypatch):
    monkeypatch.setenv("LITELLM_API_KEY", "sk-x")
    monkeypatch.setenv("LITELLM_BASE_URL", "https://h/v1")
    monkeypatch.setenv("LITELLM_CHAT_MODEL", "gpt-4o-mini")
    settings = load_settings(env_file=None)
    assert settings.chat_model == "gpt-4o-mini"
```

**Step 3: Wire ChatOrchestrator into app.py**

In `relay/src/litellm_relay/app.py`:

1. Import `ChatOrchestrator` and `ChatRequest`/`ChatResponse`
2. In `create_app()`, instantiate the orchestrator:

```python
from .chat_orchestrator import ChatOrchestrator
from .contracts import ChatRequest, ChatResponse

# inside create_app(), after service = ...
orchestrator = ChatOrchestrator(
    base_url=settings.base_url,
    api_key=settings.api_key,
    chat_model=f"litellm_proxy/{settings.chat_model}",
    research_model=f"litellm_proxy/{settings.model}",
    timeout_seconds=settings.timeout_seconds,
)

@app.post("/api/v1/chat", response_model=ChatResponse)
async def chat(payload: ChatRequest) -> ChatResponse:
    return await orchestrator.chat(payload)
```

**Step 4: Run all app tests**

```bash
cd relay && uv run pytest tests/test_app.py -v
```

Expected: all PASS

**Step 5: Run full relay suite with coverage**

```bash
cd relay && uv run pytest --cov=litellm_relay --cov-fail-under=100 --cov-report=term-missing
```

Expected: PASS, 100% coverage.

**Step 6: Commit**

```bash
git add relay/src/litellm_relay/app.py relay/src/litellm_relay/config.py relay/tests/test_app.py relay/tests/test_config.py
git commit -m "feat: add POST /api/v1/chat endpoint with auto deep_research orchestration"
```

---

## Task 5: Python client — create_chat_with_tool_calling + --auto-tool-call

**Files:**
- Modify: `clients/python/src/litellm_example/client.py`
- Modify: `clients/python/src/litellm_example/__main__.py`
- Modify: `clients/python/tests/test_client.py`
- Modify: `clients/python/tests/test_main.py`

**Step 1: Write failing tests in test_client.py**

Add to `clients/python/tests/test_client.py`:

```python
def test_create_chat_with_tool_calling_no_tool(fake_responses):
    """When the model does not call the tool, returns direct answer."""
    # First completions call: finish_reason=stop, no tool_calls
    first_response_body = json.dumps({
        "choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "Direct answer.", "tool_calls": None},
        }]
    }).encode()
    # relay /api/v1/chat response (won't be called)
    client = LiteLLMClient("https://h:4000", "key", "gpt-4o")
    # Monkeypatch the _post_json to return first response
    client._post_json = lambda url, payload: json.loads(first_response_body)
    result, tool_called = client.create_chat_with_tool_calling("Hello")
    assert result == "Direct answer."
    assert tool_called is False


def test_create_chat_with_tool_calling_with_tool(monkeypatch):
    """When model calls deep_research, client hits relay and returns final answer."""
    import json

    call_count = [0]
    relay_called = [False]

    first_body = {
        "choices": [{
            "finish_reason": "tool_calls",
            "message": {
                "role": "assistant",
                "content": None,
                "tool_calls": [{
                    "id": "call_1",
                    "type": "function",
                    "function": {
                        "name": "deep_research",
                        "arguments": json.dumps({
                            "research_question": "짜장면의 역사",
                            "deliverable_format": "markdown_brief",
                        }),
                    },
                }],
            },
        }]
    }
    relay_body = {
        "content": "연구 완료.",
        "tool_called": True,
        "tool_name": "deep_research",
        "research_summary": "요약",
    }
    second_body = {
        "choices": [{
            "finish_reason": "stop",
            "message": {"role": "assistant", "content": "최종 답변.", "tool_calls": None},
        }]
    }

    def fake_post(url, payload):
        call_count[0] += 1
        if call_count[0] == 1:
            return first_body
        if "relay" in url or "chat" in url and call_count[0] == 2:
            relay_called[0] = True
            return relay_body
        return second_body

    from litellm_example.client import LiteLLMClient
    client = LiteLLMClient("https://h:4000", "key", "gpt-4o")
    client._post_json = fake_post
    result, tool_called = client.create_chat_with_tool_calling(
        "짜장면의 역사를 알려줘",
        relay_base_url="https://h:4000",
    )
    assert tool_called is True
    assert "최종" in result or "연구" in result
```

Run: `cd clients/python && uv run pytest tests/test_client.py -v -k "tool_calling"`
Expected: FAIL

**Step 2: Implement create_chat_with_tool_calling in client.py**

Add to `LiteLLMClient` in `clients/python/src/litellm_example/client.py`:

```python
DEEP_RESEARCH_FUNCTION_TOOL: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "deep_research",
        "description": (
            "Conduct in-depth research on a topic. Use when the user asks for "
            "detailed factual information, history, analysis, or comprehensive "
            "explanations that require research beyond general knowledge."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "research_question": {"type": "string"},
                "deliverable_format": {
                    "type": "string",
                    "enum": ["markdown_brief", "markdown_report", "json_outline"],
                },
            },
            "required": ["research_question", "deliverable_format"],
        },
    },
}


def create_chat_with_tool_calling(
    self,
    prompt: str,
    relay_base_url: str | None = None,
) -> tuple[str, bool]:
    """Send a chat completions request with the deep_research function tool.

    Returns ``(answer_text, tool_was_called)``.

    When the model decides to call deep_research, this method:
    1. Calls the relay ``POST /api/v1/chat`` endpoint (or falls back to
       returning the research_summary from the relay response directly).
    2. Performs a second chat completions turn to synthesise the final answer.

    Parameters
    ----------
    prompt:
        The user message.
    relay_base_url:
        Base URL of the relay server (e.g. ``http://127.0.0.1:8080``).
        When omitted, defaults to the same ``base_url`` as the LiteLLM proxy
        (useful in tests; in production point this to the relay).
    """
    messages: list[Dict[str, Any]] = [{"role": "user", "content": prompt}]
    payload: Dict[str, Any] = {
        "model": self._model,
        "messages": messages,
        "tools": [DEEP_RESEARCH_FUNCTION_TOOL],
    }
    first_response = self._post_json(self._chat_url(), payload)

    choices = first_response.get("choices") or []
    if not choices:
        raise LiteLLMError(200, "No choices in response.", json.dumps(first_response))

    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise LiteLLMError(200, "Unexpected choice format.", json.dumps(first_response))

    finish_reason = first_choice.get("finish_reason", "stop")
    first_message = first_choice.get("message") or {}
    tool_calls = first_message.get("tool_calls") or []

    deep_research_call = next(
        (
            tc for tc in tool_calls
            if isinstance(tc, dict)
            and tc.get("type") == "function"
            and (tc.get("function") or {}).get("name") == "deep_research"
        ),
        None,
    )

    if finish_reason != "tool_calls" or deep_research_call is None:
        content = first_message.get("content") or ""
        return content, False

    # Extract tool call arguments
    raw_args = (deep_research_call.get("function") or {}).get("arguments", "{}")
    try:
        tool_args = json.loads(raw_args)
    except json.JSONDecodeError:
        tool_args = {}

    research_question = tool_args.get("research_question", prompt)
    deliverable_format = tool_args.get("deliverable_format", "markdown_brief")
    tool_call_id = deep_research_call.get("id", "call_0")

    # Call relay /api/v1/chat to get research result
    relay_url = relay_base_url or self._base_url.rstrip("/").replace("/v1/", "").replace("/v1", "")
    relay_chat_url = relay_url.rstrip("/") + "/api/v1/chat"
    relay_payload: Dict[str, Any] = {
        "message": research_question,
        "auto_tool_call": True,
    }
    relay_response = self._post_json(relay_chat_url, relay_payload)
    research_summary = relay_response.get("research_summary") or relay_response.get("content") or ""

    # Second turn: synthesise final answer
    messages_with_result: list[Dict[str, Any]] = [
        {"role": "user", "content": prompt},
        {"role": "assistant", "content": None, "tool_calls": [deep_research_call]},
        {"role": "tool", "tool_call_id": tool_call_id, "content": research_summary},
    ]
    second_payload: Dict[str, Any] = {
        "model": self._model,
        "messages": messages_with_result,
    }
    second_response = self._post_json(self._chat_url(), second_payload)
    second_choices = second_response.get("choices") or []
    if not second_choices:
        return research_summary, True
    second_message = (second_choices[0] or {}).get("message") or {}
    final_content = second_message.get("content") or research_summary

    return final_content, True
```

Then add `LiteLLMClient.create_chat_with_tool_calling = create_chat_with_tool_calling` inside the class (as an instance method, not standalone).

**Step 3: Add --auto-tool-call to __main__.py**

In `clients/python/src/litellm_example/__main__.py`, add:

```python
# After --web-search parsing:
auto_tool_call = "--auto-tool-call" in sys.argv

# In main execution section:
if auto_tool_call:
    relay_base = os.environ.get("RELAY_BASE_URL", "http://127.0.0.1:8080")
    result, tool_called = client.create_chat_with_tool_calling(prompt, relay_base_url=relay_base)
    print(result)
    if tool_called:
        print("[deep_research was called automatically]", file=sys.stderr)
```

**Step 4: Run python tests with coverage**

```bash
cd clients/python && uv run pytest --cov=litellm_example --cov-fail-under=100 --cov-report=term-missing
```

Expected: PASS, 100%

**Step 5: Commit**

```bash
git add clients/python/src/litellm_example/client.py clients/python/src/litellm_example/__main__.py clients/python/tests/test_client.py clients/python/tests/test_main.py
git commit -m "feat: add Python client-side function calling (--auto-tool-call)"
```

---

## Task 6: Java client — createChatWithToolCalling + --auto-tool-call

**Files:**
- Modify: `clients/java/src/main/java/example/litellm/LiteLlmClient.java`
- Modify: `clients/java/src/main/java/example/litellm/relay/RelayClient.java`
- Modify: `clients/java/src/main/java/example/litellm/Main.java`
- Modify: `clients/java/src/test/java/example/litellm/LiteLlmClientTest.java`
- Modify: `clients/java/src/test/java/example/litellm/RelayClientTest.java`
- Modify: `clients/java/src/test/java/example/litellm/MainTest.java`

**Step 1: Add invokeChat to RelayClient**

In `RelayClient.java`, add:

```java
public ChatResult invokeChat(String message, boolean autoToolCall) {
    Map<String, Object> body = new LinkedHashMap<>();
    body.put("message", message);
    body.put("auto_tool_call", autoToolCall);
    JsonNode result = postJson(chatUrl(), body);
    String content = result.path("content").asText("");
    boolean toolCalled = result.path("tool_called").asBoolean(false);
    String toolName = result.hasNonNull("tool_name") ? result.get("tool_name").asText() : null;
    String summary = result.hasNonNull("research_summary") ? result.get("research_summary").asText() : null;
    return new ChatResult(content, toolCalled, toolName, summary);
}

private URI chatUrl() {
    return baseUrl.resolve("api/v1/chat");
}

public record ChatResult(String content, boolean toolCalled, String toolName, String researchSummary) {}
```

**Step 2: Add createChatWithToolCalling to LiteLlmClient**

In `LiteLlmClient.java`:

```java
private static final Map<String, Object> DEEP_RESEARCH_TOOL_SCHEMA = Map.of(
    "type", "function",
    "function", Map.of(
        "name", "deep_research",
        "description", "Conduct in-depth research on a topic.",
        "parameters", Map.of(
            "type", "object",
            "properties", Map.of(
                "research_question", Map.of("type", "string"),
                "deliverable_format", Map.of(
                    "type", "string",
                    "enum", List.of("markdown_brief", "markdown_report", "json_outline")
                )
            ),
            "required", List.of("research_question", "deliverable_format")
        )
    )
);

/**
 * Chat completions with automatic deep_research function calling.
 *
 * @param prompt       user message
 * @param relayBaseUrl relay server base URL (e.g. http://127.0.0.1:8080)
 * @return [final answer, toolWasCalled]
 */
public String[] createChatWithToolCalling(String prompt, String relayBaseUrl) {
    Map<String, Object> payload = new LinkedHashMap<>();
    payload.put("model", model);
    payload.put("messages", List.of(Map.of("role", "user", "content", prompt)));
    payload.put("tools", List.of(DEEP_RESEARCH_TOOL_SCHEMA));

    JsonNode first = postJson(baseUrl.resolve("chat/completions"), payload);
    JsonNode firstChoice = first.path("choices").get(0);
    String finishReason = firstChoice.path("finish_reason").asText("stop");
    JsonNode firstMessage = firstChoice.path("message");
    JsonNode toolCallsNode = firstMessage.path("tool_calls");

    if (!"tool_calls".equals(finishReason) || !toolCallsNode.isArray() || toolCallsNode.isEmpty()) {
        return new String[]{firstMessage.path("content").asText(""), "false"};
    }

    JsonNode tc = toolCallsNode.get(0);
    String toolCallId = tc.path("id").asText("call_0");
    String rawArgs = tc.path("function").path("arguments").asText("{}");
    JsonNode argsNode;
    try {
        argsNode = MAPPER.readTree(rawArgs);
    } catch (JsonProcessingException e) {
        argsNode = MAPPER.createObjectNode();
    }
    String researchQuestion = argsNode.path("research_question").asText(prompt);

    // Call relay /api/v1/chat
    URI relayUri = URI.create(relayBaseUrl.endsWith("/") ? relayBaseUrl : relayBaseUrl + "/");
    Map<String, Object> relayBody = Map.of("message", researchQuestion, "auto_tool_call", true);
    JsonNode relayResp = postJson(relayUri.resolve("api/v1/chat"), relayBody);
    String researchSummary = relayResp.path("research_summary").asText(
        relayResp.path("content").asText(""));

    // Second turn
    List<Map<String, Object>> messagesWithResult = List.of(
        Map.of("role", "user", "content", prompt),
        Map.of("role", "assistant", "content", "", "tool_calls", List.of(Map.of(
            "id", toolCallId, "type", "function",
            "function", Map.of("name", "deep_research", "arguments", rawArgs)))),
        Map.of("role", "tool", "tool_call_id", toolCallId, "content", researchSummary)
    );
    Map<String, Object> second = new LinkedHashMap<>();
    second.put("model", model);
    second.put("messages", messagesWithResult);
    JsonNode secondResp = postJson(baseUrl.resolve("chat/completions"), second);
    String finalContent = secondResp.path("choices").get(0).path("message").path("content").asText(researchSummary);

    return new String[]{finalContent, "true"};
}
```

**Step 3: Add --auto-tool-call to Main.java**

```java
case "--auto-tool-call" -> autoToolCall = true;
```

And in execution:

```java
if (autoToolCall) {
    String relayUrl = System.getenv("RELAY_BASE_URL");
    if (relayUrl == null) relayUrl = "http://127.0.0.1:8080";
    String[] result = client.createChatWithToolCalling(prompt, relayUrl);
    content = result[0];
    if ("true".equals(result[1])) {
        System.err.println("[deep_research was called automatically]");
    }
}
```

**Step 4: Add tests**

In `LiteLlmClientTest.java`, add tests for `createChatWithToolCalling` with mock HttpClient returning:
- first call: tool_calls response
- relay call: research_summary response
- second call: final content response

In `RelayClientTest.java`, add test for `invokeChat`.

In `MainTest.java`, add test for `--auto-tool-call` flag.

**Step 5: Run Java tests**

```bash
cd clients/java && mvn test
```

Expected: BUILD SUCCESS

**Step 6: Commit**

```bash
git add clients/java/
git commit -m "feat: add Java client-side function calling (--auto-tool-call) and relay invokeChat"
```

---

## Task 7: Evaluate Approach B (Responses API function calling)

**Goal:** Test whether `POST /v1/responses` supports `tools=[{type:"function", ...}]` for function calling via LiteLLM Proxy with gpt-4o. Document results in manual.

**Step 1: Add an evaluation script**

Create `clients/python/scripts/eval_responses_function_calling.py`:

```python
#!/usr/bin/env python3
"""Evaluate whether the Responses API supports function calling via LiteLLM Proxy.

Run:
  LITELLM_MODEL=gpt-4o uv run python scripts/eval_responses_function_calling.py
"""
import json, os, sys
sys.path.insert(0, "src")
from litellm_example.client import LiteLLMClient, DEEP_RESEARCH_FUNCTION_TOOL

base_url = os.environ["LITELLM_BASE_URL"]
api_key = os.environ["LITELLM_API_KEY"]
model = os.environ.get("LITELLM_MODEL", "gpt-4o")

client = LiteLLMClient(base_url, api_key, model)
payload = {
    "model": model,
    "input": "짜장면의 역사를 자세히 설명해줘",
    "tools": [DEEP_RESEARCH_FUNCTION_TOOL],
}
try:
    result = client._post_json(client._responses_url(), payload)
    print("SUCCESS:", json.dumps(result, ensure_ascii=False, indent=2)[:500])
except Exception as e:
    print(f"FAIL: {e}")
```

**Step 2: Run and record result**

```bash
cd clients/python && LITELLM_MODEL=gpt-4o uv run python scripts/eval_responses_function_calling.py
```

Record result in manual section 13-4.

**Step 3: Commit eval script**

```bash
git add clients/python/scripts/eval_responses_function_calling.py
git commit -m "chore: add Responses API function calling evaluation script"
```

---

## Task 8: Documentation

**Files:**
- Create: `docs/ko/auto-toolcalling.md`
- Modify: `docs/ko/manual.md` (add section 13)
- Modify: `docs/ko/relay-example.md` (document /api/v1/chat)
- Modify: `mkdocs.yml` (add auto-toolcalling page)

**Step 1: Create docs/ko/auto-toolcalling.md**

Full standalone page with:
- 개념 설명 (function calling 원리)
- Approach A (client-side) Python 예제
- Approach A (client-side) Java 예제
- Approach C (relay-side) `/api/v1/chat` 예제
- Approach B (Responses API) 평가 결과
- 평가 매트릭스 (실제 테스트 결과 기록)
- 모델별 지원 현황

**Step 2: Add section 13 to manual.md**

Summary section covering all three approaches with cross-links to auto-toolcalling.md.

**Step 3: Update relay-example.md**

Add `/api/v1/chat` endpoint documentation with example curl.

**Step 4: Update mkdocs.yml**

Add `자동 Tool Calling: ko/auto-toolcalling.md` to nav under 예제 section.

**Step 5: Verify mkdocs**

```bash
mkdocs build --strict
```

**Step 6: Commit**

```bash
git add docs/ mkdocs.yml
git commit -m "docs: document auto tool-calling examples and evaluation (section 13 + standalone page)"
```

---

## Task 9: Final verification + push

**Step 1: Run all tests**

```bash
cd relay && uv run pytest --cov=litellm_relay --cov-fail-under=100
cd clients/python && uv run pytest --cov=litellm_example --cov-fail-under=100
cd clients/java && mvn test
mkdocs build --strict
```

Expected: all pass

**Step 2: Push to main**

```bash
git push origin main
```

**Step 3: Verify CI passes and GitHub Pages is deployed**

Check: `https://github.com/seonghobae/litellm-o3-deep-research-rest-examples/actions`
Check: `https://seonghobae.github.io/litellm-o3-deep-research-rest-examples/`

---

## Summary of all tasks

| Task | Description | Scope |
|------|-------------|-------|
| 0 | Fix doc section numbering (9-1→11-1) | docs bug fix |
| 1 | Add GitHub Pages CI deploy | CI fix |
| 2 | ChatRequest/ChatResponse contracts | relay |
| 3 | ChatOrchestrator implementation + tests | relay |
| 4 | POST /api/v1/chat endpoint | relay |
| 5 | Python --auto-tool-call | python client |
| 6 | Java --auto-tool-call + invokeChat | java client |
| 7 | Evaluate Responses API function calling | evaluation |
| 8 | Full documentation | docs |
| 9 | Final verification + push | CI/CD |
