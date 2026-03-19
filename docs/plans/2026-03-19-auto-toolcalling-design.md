# Auto Tool-Calling Deep Research Design

**Date:** 2026-03-19  
**Status:** Approved — proceeding to implementation  
**Session context:** This design was derived after reviewing the current repo state (commit `3fa76ba`, branch `main`).

---

## Current Issues to Fix

1. **`docs/ko/manual.md` section numbering bug**: After section 10 (text_format), section 11 reuses sub-section numbers `9-1` through `9-7` — these should be `11-1` through `11-7`.
2. **GitHub Pages deployment missing from CI**: The `docs` job in `.github/workflows/ci.yml` only runs `mkdocs build --strict` but never deploys to `gh-pages`. The site is built but not published. A `gh-pages` deploy step must be added.
3. **Auto tool-calling ("일반 대화 중 deep research 자동 개입") not implemented yet**: All current patterns require the caller to explicitly invoke `POST /api/v1/tool-invocations`. There is no example where a model autonomously decides to call deep_research.

---

## Auto Tool-Calling: What It Means

"일반 대화 중 deep research가 개입되는 상황"은 OpenAI의 function calling 패턴에 해당합니다:

1. 사용자가 일반 chat 메시지를 보냄 ("짜장면의 역사를 자세히 알려줘")
2. 모델(gpt-4o)이 `tools` 정의를 보고 "이 질문은 deep_research 도구가 필요하다"고 스스로 판단
3. 모델이 `finish_reason: tool_calls`로 응답하며 `deep_research` function call 인수를 반환
4. 클라이언트(또는 relay)가 실제 deep research를 실행하고 결과를 conversation에 붙임
5. 모델이 tool 결과를 읽고 최종 자연어 응답을 생성

이것이 "자동 개입"의 핵심입니다. 모델이 능동적으로 tool call 여부를 결정합니다.

---

## Approach Decision

두 가지를 모두 구현해서 비교합니다.

### Approach A: Client-Side Function Calling (Python + Java 예제 확장)

- `LiteLLMClient` / `LiteLlmClient`에 `create_chat_with_tool_calling()` 메서드 추가
- `POST /v1/chat/completions`에 `tools=[{type:"function", function:{name:"deep_research", ...}}]` 포함
- `finish_reason == "tool_calls"` 감지 → relay 호출 → tool result → 2차 chat completions → 최종 텍스트 반환
- CLI: `--auto-tool-call` 플래그 추가 (Python/Java 둘 다)

### Approach C: Relay-Side Orchestration (relay 새 엔드포인트)

- relay에 `POST /api/v1/chat` 엔드포인트 추가
- 내부 orchestration:
  1. gpt-4o 1차 chat completions (tools 포함)
  2. tool_calls 발생 시 `invoke_deep_research()` 자동 실행
  3. tool 결과를 messages에 추가 후 2차 completions
  4. 최종 assistant 텍스트 반환
- 클라이언트는 단순 chat 요청만 보냄 — deep research 개입 완전 투명

### Approach B: Responses API tool calling (평가 대상)

- `POST /v1/responses`에 `tools=[{type:"function", ...}]` 추가
- LiteLLM Proxy의 Responses API function calling 지원 여부는 모델 종속 → 테스트 후 결과 기록
- 지원하면 Approach A의 대안으로 문서화, 지원 안 하면 제한 사항으로 명시

---

## Implementation Scope

### Bug Fixes (Task 0)
- Fix section numbering in `docs/ko/manual.md` (11-1~11-7 not 9-1~9-7)
- Add `mkdocs gh-deploy` to CI workflow for GitHub Pages publishing

### New Features (Tasks 1–5)
1. **relay: `POST /api/v1/chat` endpoint** — relay-side orchestration
   - New file: `relay/src/litellm_relay/chat_orchestrator.py`
   - New endpoint in `relay/src/litellm_relay/app.py`
   - Tests: `relay/tests/test_chat_orchestrator.py`
   - 100% coverage maintained

2. **relay contracts: `ChatRequest` / `ChatResponse`** — new Pydantic models
   - `ChatRequest`: `message: str`, `context: list[str]`, `auto_tool_call: bool = True`
   - `ChatResponse`: `content: str`, `tool_called: bool`, `tool_name: str | None`, `research_summary: str | None`

3. **Python client: `--auto-tool-call` flag + client-side function calling**
   - `LiteLLMClient.create_chat_with_tool_calling(prompt)` method
   - CLI `--auto-tool-call` flag
   - Tests: extend `test_client.py`, `test_main.py` (100% coverage)

4. **Java client: `--auto-tool-call` flag + client-side function calling**
   - `LiteLlmClient.createChatWithToolCalling(prompt)` method
   - CLI `--auto-tool-call` flag
   - Tests: extend `MainTest.java`, `LiteLlmClientTest.java`

5. **Documentation + evaluation**
   - New section 13 in `docs/ko/manual.md`: Auto Tool Calling
   - `docs/ko/relay-example.md`: document new `/api/v1/chat` endpoint
   - Evaluation matrix: client-side vs relay-side, Responses API support

### Constraints (Recorded Decisions)

- **Coverage gate**: relay 100%, python 100%, java BUILD SUCCESS — must stay green
- **mkdocs build --strict** must pass after all doc changes
- **No new external dependencies** beyond what's already in pyproject.toml / pom.xml (Jackson already present, no new Python packages needed)
- **Java relay chat**: Java relay client already uses `RelayClient`; extend it with `invokeChat()` method
- **function calling only on gpt-4o**: o3-deep-research does not support standard function calling (it is a research model with its own internal tool-use); the auto tool-calling feature targets gpt-4o as the orchestrating LLM
- **LITELLM_MODEL env var**: when `LITELLM_MODEL=o3-deep-research`, auto tool-calling uses gpt-4o for the orchestration layer and o3-deep-research (via relay) for the actual deep_research tool execution
- **Approach B (Responses API function calling)**: evaluate first, document results, do not block on it
- **GitHub Pages deploy**: use `mkdocs gh-deploy --force` in CI; requires `GITHUB_TOKEN` (already available in Actions); add as separate job step after `mkdocs build --strict`

---

## New File List

```
relay/src/litellm_relay/chat_orchestrator.py   (NEW)
relay/tests/test_chat_orchestrator.py          (NEW)
docs/ko/auto-toolcalling.md                    (NEW - standalone page)
docs/plans/2026-03-19-auto-toolcalling-design.md  (THIS FILE)
```

### Modified Files

```
relay/src/litellm_relay/contracts.py           (ChatRequest, ChatResponse models)
relay/src/litellm_relay/app.py                 (POST /api/v1/chat endpoint)
relay/tests/test_app.py                        (new endpoint tests)
clients/python/src/litellm_example/client.py  (create_chat_with_tool_calling)
clients/python/src/litellm_example/__main__.py (--auto-tool-call flag)
clients/python/tests/test_client.py           (new method tests)
clients/python/tests/test_main.py             (new flag tests)
clients/java/.../LiteLlmClient.java           (createChatWithToolCalling)
clients/java/.../relay/RelayClient.java       (invokeChat)
clients/java/.../Main.java                    (--auto-tool-call flag)
clients/java/.../LiteLlmClientTest.java
clients/java/.../RelayClientTest.java
clients/java/.../MainTest.java
docs/ko/manual.md                             (fix numbering, add section 13)
docs/ko/relay-example.md                      (document /api/v1/chat)
mkdocs.yml                                    (add auto-toolcalling page)
.github/workflows/ci.yml                      (add gh-deploy step)
ARCHITECTURE.md                               (update)
```

---

## API Contract: New `/api/v1/chat`

### Request

```json
POST /api/v1/chat
{
  "message": "짜장면의 역사를 자세히 알려줘",
  "context": [],
  "auto_tool_call": true
}
```

### Response (tool was called)

```json
{
  "content": "짜장면은 19세기 말 중국 산둥 지방 출신 이민자들이...(최종 자연어 응답)",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "짜장면의 역사: 인천 차이나타운 기원..."
}
```

### Response (tool was NOT called)

```json
{
  "content": "안녕하세요! 무엇을 도와드릴까요?",
  "tool_called": false,
  "tool_name": null,
  "research_summary": null
}
```

---

## The `deep_research` Function Schema (for Chat Completions tools)

```json
{
  "type": "function",
  "function": {
    "name": "deep_research",
    "description": "Conduct in-depth research on a topic and return a detailed report. Use this when the user asks for detailed factual information, history, analysis, or comprehensive explanations that require research beyond general knowledge.",
    "parameters": {
      "type": "object",
      "properties": {
        "research_question": {
          "type": "string",
          "description": "The specific research question or topic to investigate"
        },
        "deliverable_format": {
          "type": "string",
          "enum": ["markdown_brief", "markdown_report", "json_outline"],
          "description": "Format of the research output"
        }
      },
      "required": ["research_question", "deliverable_format"]
    }
  }
}
```

---

## Evaluation Matrix (to be filled during implementation)

| Scenario | Result |
|----------|--------|
| Approach A: Python client-side function calling (gpt-4o) | TBD |
| Approach A: Java client-side function calling (gpt-4o) | TBD |
| Approach C: relay-side `/api/v1/chat` orchestration (gpt-4o) | TBD |
| Approach B: Responses API function calling (gpt-4o) | TBD |
| Auto-trigger: topic clearly needs research → tool called | TBD |
| Auto-trigger: simple greeting → tool NOT called | TBD |
| Auto-trigger: relay-side + Java caller | TBD |
