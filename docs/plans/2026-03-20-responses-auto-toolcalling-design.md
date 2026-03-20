# Responses API Auto Tool Calling Design

## Context

- 현재 repository의 auto tool calling은 Python direct client, Java direct client, relay `POST /api/v1/chat` 모두 Chat Completions의 `tool_calls` 흐름에 맞춰 구현되어 있다.
- 실제 deep research 실행 자체는 relay 내부에서 이미 Responses API를 사용하지만, orchestration turn은 여전히 Chat Completions에 묶여 있다.
- 사용자 요구사항은 auto tool calling 자체를 OpenAI Responses API 기준으로 바꾸는 것이다.

## Constraints

- 공개 CLI 표면(`--auto-tool-call`)과 relay 공개 엔드포인트(`POST /api/v1/chat`)는 유지한다.
- API 변경은 `docs/security/api-security-checklist.md`를 따라 raw upstream internals를 외부에 노출하지 않아야 한다.
- repo acceptance criteria, Korean manuals, architecture 문서는 실제 코드와 동시에 갱신되어야 한다.
- 구현은 TDD로 진행하고, Python/Java/relay 회귀 테스트와 docs build를 모두 통과해야 한다.

## Approaches

### Approach A — Relay만 Responses API로 바꾸고 direct client는 기존 유지

- 장점: 최소 변경.
- 단점: user가 요구한 "Auto Tool Calling은 Responses API"를 direct client 경로에서 충족하지 못한다.
- 결론: 불충분.

### Approach B — Direct client는 Responses API로 바꾸고 relay `/api/v1/chat`는 유지

- 장점: CLI 표면은 빠르게 맞출 수 있다.
- 단점: relay auto tool calling 경로는 계속 Chat Completions 기반이라 repo 전체 동작이 이원화된다.
- 결론: 부분 충족에 그친다.

### Approach C — Python/Java direct client와 relay orchestration 전체를 Responses API 기반으로 통일

- 장점: repo 전체 auto tool calling semantics가 하나로 정리되고 docs/acceptance도 명확해진다.
- 단점: 테스트와 문서 수정 범위가 가장 넓다.
- 결론: 권장. 이번 canonical task로 채택한다.

## Chosen Design

- Auto tool calling의 표준 흐름을 Responses API 2-step 패턴으로 통일한다.
  1. 첫 번째 `POST /v1/responses` 요청에서 `tools=[function]`를 전달한다.
  2. 응답의 `output[]`에서 `type == "function_call"` 항목을 찾는다.
  3. 함수 호출 결과를 실행한 뒤 두 번째 `POST /v1/responses` 요청에 `previous_response_id`와 `function_call_output` input item을 전달한다.
  4. 두 번째 응답의 텍스트를 최종 답변으로 반환한다.
- Relay `POST /api/v1/chat`의 공개 request/response schema는 유지하고, 내부 orchestration만 Responses API로 교체한다.
- Python/Java direct client의 `--auto-tool-call`도 같은 패턴을 사용하되, relay 실행 단계에서는 `/api/v1/tool-invocations`를 호출해 structured args를 그대로 넘긴다. 이렇게 해야 `deliverable_format` 같은 tool arguments가 손실되지 않는다.

## Component Changes

### Relay

- `ChatOrchestrator`는 `litellm.completion()` 대신 `litellm.responses()`를 사용한다.
- `ChatRequest`를 Responses API input으로 변환하고, `output[]`에서 `function_call`을 파싱하는 helper를 추가한다.
- deep research 완료 후 `previous_response_id` + `function_call_output`으로 second turn을 수행한다.
- first/second turn 실패, malformed function_call payload도 redacted `ChatResponse`로 반환한다.

### Python direct client

- `create_chat_with_tool_calling()`를 Responses API 기반으로 교체한다.
- relay 호출 대상을 `/api/v1/chat`에서 `/api/v1/tool-invocations` foreground path로 바꾼다.
- tool arguments에서 `deliverable_format`를 유지하고, relay 결과의 `output_text`를 function output으로 second turn에 전달한다.

### Java direct client

- Python과 동일한 semantics를 `LiteLlmClient#createChatWithToolCalling`에 반영한다.
- `previous_response_id` + `function_call_output` payload를 직렬화하는 helper를 추가한다.

### Docs

- acceptance criteria, architecture, Korean manuals에서 "Chat Completions tool_calls" 설명을 "Responses API function_call/function_call_output"로 교체한다.
- 기존 Responses API function-calling이 "평가" 라고 적힌 문구는 실제 canonical path로 승격한다.

## Testing Strategy

- Relay: first response function_call detection, continuation payload shape, malformed args fallback, first/second call redacted errors.
- Python: no-tool path, function_call path, relay tool invocation payload preservation, final answer extraction, fallback on missing second output.
- Java: Python과 동일한 회귀 케이스.
- Full verification: relay pytest 100% coverage, python pytest 100% coverage, Java `mvn test`, `mkdocs build --strict`.

## Decisions

- Auto tool calling canonical path는 Responses API다.
- Direct clients는 relay `/api/v1/chat`를 tool executor로 재사용하지 않는다.
- Relay public `/api/v1/chat` contract는 유지한다.
- 에러는 기존 redaction 원칙을 유지한다.
