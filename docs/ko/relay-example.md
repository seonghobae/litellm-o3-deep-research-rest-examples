# Relay 중계 예제

## 무엇을 구현했나요?

`relay/` 예제는 LiteLLM Python SDK를 감싼 FastAPI + Hypercorn 서버입니다.

외부 계약은 raw `input` 문자열이 아니라 다음과 같은 구조화된 tool invocation 형식입니다.

| 필드 | 타입 | 설명 |
|------|------|------|
| `tool_name` | `"deep_research"` | 고정값 |
| `arguments.research_question` | `string` | 조사할 주제·질문 |
| `arguments.system_prompt` | `string?` | 모델 수준 지시문 (system/developer prompt). 미설정 시 생략 |
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
- `RELAY_TIMEOUT_SECONDS` (선택, 기본 `30`)

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
- `GET /api/v1/tool-invocations/{invocation_id}`
- `GET /api/v1/tool-invocations/{invocation_id}/wait`
- `GET /api/v1/tool-invocations/{invocation_id}/events`

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
- background invocation은 `invocation_id`, `upstream_response_id`, `status` 중심 메타데이터를 반환합니다.
- stream invocation은 `text/event-stream` 형태의 SSE를 반환하며, 현재 예제는 text delta만 중계합니다.

## 관련 문서

- [Responses / Background / Relay 스트리밍](responses-guide.md)
- [중계 예제 구현 계획(보관)](relay-toolcalling-plan.md)
