# Relay 중계 예제

## 무엇을 구현했나요?

`relay/` 예제는 LiteLLM Python SDK를 감싼 FastAPI + Hypercorn 서버입니다.

외부 계약은 raw `input` 문자열이 아니라 다음과 같은 구조화된 tool invocation 형식입니다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `tool_name` | `"deep_research"` | 고정값 |
| `arguments.research_question` | `string` | 조사할 주제·질문 |
| `arguments.system_prompt` | `string?` | 모델 수준 지시문 (system/developer prompt). 미설정 시 생략 |
| `arguments.text_format` | `object?` | API 레벨 JSON 강제. `{"type":"json_object"}` 또는 `{"type":"json_schema",...}`. 미설정 시 plain text |
| `arguments.context` | `string[]` | 추가 배경 정보 |
| `arguments.constraints` | `string[]` | 출력 형식·범위 제약 |
| `arguments.deliverable_format` | `"markdown_brief" \| "markdown_report" \| "json_outline"` | 산출물 형식 |
| `arguments.require_citations` | `bool` | 인용 요구 여부 (기본 `true`) |
| `arguments.background` | `bool` | 비동기 제출 여부 |
| `arguments.stream` | `bool` | SSE 스트림 사용 여부 |

즉, Java 호출자는 relay에 도메인 지향적인 요청만 보내고, relay 내부에서만 LiteLLM SDK 호출로 번역합니다.

## 필요한 환경 변수

relay 서버는 direct Python 예제와 같은 upstream 설정을 사용합니다.

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택, 기본 `o3-deep-research`)
- `RELAY_HOST` (선택, 기본 `127.0.0.1`)
- `RELAY_PORT` (선택, 기본 `8080`)
- `RELAY_TIMEOUT_SECONDS` (선택, 기본 `30`) — Responses orchestration 턴 타임아웃
- `RELAY_RESEARCH_TIMEOUT_SECONDS` (선택, 기본 `300`) — deep_research 실행 타임아웃 (`/api/v1/chat` 자동 tool calling 시 deep_research는 이 값을 사용)
- `LITELLM_CHAT_MODEL` (선택, 기본 `gpt-4o`) — `POST /api/v1/chat` orchestration에 사용하는 모델 (Responses API function calling 지원 모델이어야 함)
- `RELAY_MAX_INVOCATIONS` (선택, 기본 `1024`) — 메모리에 유지할 최대 invocation 수
- `RELAY_MAX_STREAM_BYTES` (선택, 기본 `1000000`) — stream invocation 하나가 메모리에 유지할 최대 UTF-8 바이트 수

direct Python/Java 예제와 달리 relay는 `LITELLM_BASE_URL`을 LiteLLM SDK의 `api_base`로 그대로 전달합니다. 따라서 upstream LiteLLM Proxy가 허용하는 root URL 또는 `/v1` URL을 사용할 수 있습니다.

Java relay caller는 다음 값을 선택적으로 사용합니다.

- `RELAY_BASE_URL` (기본 `http://127.0.0.1:8080`)

## 실행

```bash
cd relay
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_relay
```

## 공개 API

- `POST /api/v1/tool-invocations`
- `GET /api/v1/tool-invocations/{invocation_id}` (`X-Invocation-Token` 필요)
- `GET /api/v1/tool-invocations/{invocation_id}/wait` (`X-Invocation-Token` 필요)
- `GET /api/v1/tool-invocations/{invocation_id}/events` (`X-Invocation-Token` 필요)

## 요청 예시

### 기본 호출

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "Azure OpenAI o3-deep-research relay 구조를 설명해줘",
    "context": ["Azure Landing Zone", "LiteLLM Proxy"],
    "constraints": ["markdown 형식", "보안 경계 설명"],
    "deliverable_format": "markdown_brief",
    "require_citations": true,
    "background": false,
    "stream": false
  }
}
```

### system_prompt 포함 호출

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "짜장면의 역사를 설명해줘",
    "deliverable_format": "markdown_brief",
    "system_prompt": "당신은 초등학생에게 설명하는 선생님입니다. 최대 2문장으로 쉬운 말로 설명하세요.",
    "require_citations": false
  }
}
```

`system_prompt`는 Responses API의 `instructions` 필드로 전달됩니다. 모델이 **user 질문과 별개로** 페르소나·출력 언어·형식을 지키도록 강제할 때 사용합니다.

### text_format 포함 호출 — json_object

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "짜장면의 기원을 JSON으로: origin_country, year_introduced, main_ingredient 키 포함",
    "deliverable_format": "json_outline",
    "text_format": {"type": "json_object"},
    "require_citations": false
  }
}
```

### text_format 포함 호출 — json_schema (strict)

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "짜장면의 역사를 JSON으로 반환해줘",
    "deliverable_format": "json_outline",
    "text_format": {
      "type": "json_schema",
      "name": "food_history",
      "strict": true,
      "schema": {
        "type": "object",
        "properties": {
          "origin_country":      {"type": "string"},
          "introduced_to_korea": {"type": "integer"},
          "key_milestone":       {"type": "string"},
          "is_fusion":           {"type": "boolean"}
        },
        "required": ["origin_country","introduced_to_korea","key_milestone","is_fusion"],
        "additionalProperties": false
      }
    },
    "require_citations": false
  }
}
```

> **주의:** `text_format`은 gpt-4o 계열에서 완전 지원됩니다. `o3-deep-research`는 `json_schema`를 API 400으로 거부하고, `json_object`는 API 레벨에서 수용될 수 있지만 실제 JSON object 준수는 보장되지 않습니다.

## Java에서 relay 호출

포그라운드 호출:

```bash
cd clients/java
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay Summarize relay architecture"
```

백그라운드 제출:

```bash
cd clients/java
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay --background Summarize relay architecture"
```

스트림 모드:

```bash
cd clients/java
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay --stream Summarize relay architecture"
```

## 구현 포인트

- relay 내부에서는 LiteLLM SDK를 `litellm_proxy/<model>` 형태로 사용합니다.
- foreground invocation은 바로 최종 텍스트를 반환합니다.
- background invocation은 `invocation_id`, `invocation_token`, `upstream_response_id`, `status` 중심 메타데이터를 반환합니다.
- stream invocation은 `text/event-stream` 형태의 SSE를 반환하며, 현재 예제는 text delta만 중계합니다.
- chat/SSE 오류 응답은 구조화되어 반환되며, raw upstream 예외 문자열 대신 안전한 public 메시지만 노출합니다.

## 새 엔드포인트: POST /api/v1/chat (자동 Tool Calling)

relay에 `POST /api/v1/chat` 엔드포인트가 추가되었습니다. 이 엔드포인트는 일반 대화 요청을 받아 모델이 스스로 deep_research tool 호출 여부를 결정하는 **relay-side 자동 orchestration helper**를 제공합니다. 표준 OpenAI 호환 흐름은 내부적으로 `POST /v1/responses`의 `function_call` / `function_call_output` 패턴을 사용합니다.

### 요청

```json
{
  "message": "짜장면의 역사를 자세히 알려줘",
  "context": [],
  "auto_tool_call": true
}
```

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `message` | string | 필수 | 사용자 메시지 |
| `context` | list[string] | `[]` | 추가 맥락 (user 메시지 앞에 붙음) |
| `auto_tool_call` | bool | `true` | `false`이면 tool schema 없이 직접 답변 |
| `system_prompt` | string \| null | `null` | deep_research 실행 시 Responses API `instructions` 필드로 전달. 페르소나·출력 언어·형식 강제에 사용. |
| `deliverable_format` | string | `"markdown_brief"` | deep_research 산출물 형식 폴백. 모델이 tool call 인자로 형식을 지정하면 모델 지정값이 우선. |

### 응답

```json
{
  "content": "짜장면의 역사는...",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "# 짜장면의 역사\n..."
}
```

| 필드 | 타입 | 설명 |
|------|------|------|
| `content` | string | 최종 자연어 답변 |
| `tool_called` | bool | deep_research가 호출됐는지 여부 |
| `tool_name` | string \| null | 호출된 tool 이름 (`"deep_research"` 또는 `null`) |
| `research_summary` | string \| null | deep_research의 실제 연구 결과 요약 |

### system_prompt 사용 예시

```bash
# deep_research 결과를 항상 영어로 받기
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사를 자세히 알려줘",
    "auto_tool_call": true,
    "system_prompt": "Always answer in English only."
  }'
```

```bash
# 초등학생 페르소나로 답변 요청
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사를 알려줘",
    "auto_tool_call": true,
    "system_prompt": "당신은 초등학생에게 설명하는 선생님입니다. 쉬운 말로 2문장으로만 답하세요."
  }'
```

`system_prompt`는 deep_research tool이 실제로 호출될 때만 적용됩니다. 모델이 tool 호출 없이 직접 답변하는 경우에는 영향을 주지 않습니다.

### deliverable_format 사용 예시

```bash
# 상세 보고서 형식으로 요청
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사와 사회적 영향을 상세히 알려줘",
    "auto_tool_call": true,
    "deliverable_format": "markdown_report"
  }'
```

모델이 tool call 인자에서 `deliverable_format`을 직접 지정하면 모델 지정값이 우선됩니다. 지정하지 않으면 이 필드의 값이 폴백으로 사용됩니다.

### Java에서 system_prompt 및 deliverable_format 사용

```java
import example.litellm.relay.RelayClient;
import java.time.Duration;

RelayClient client = new RelayClient("http://127.0.0.1:8080", Duration.ofSeconds(120));

// system_prompt와 deliverable_format 지정
RelayClient.ChatResult result = client.invokeChat(
    "짜장면의 역사를 자세히 알려줘",
    true,                                       // auto_tool_call
    "Always answer in English only.",           // system_prompt
    "markdown_report"                           // deliverable_format
);
System.out.println(result.content());
```

2-인자 버전(`invokeChat(message, autoToolCall)`)은 `system_prompt=null`, `deliverable_format="markdown_brief"`를 기본값으로 사용합니다.

### relay 설정

```bash
LITELLM_CHAT_MODEL=gpt-4o
LITELLM_MODEL=o3-deep-research
uv run python -m litellm_relay
```

자세한 내용은 [자동 Tool Calling 가이드](auto-toolcalling.md)를 참고하세요.

## 관련 문서

- [Responses / Background / Relay 스트리밍](responses-guide.md)
- [중계 예제 구현 계획(보관)](relay-toolcalling-plan.md)
- [자동 Tool Calling 가이드](auto-toolcalling.md)
