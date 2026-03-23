# Java 직접 호출 예제

## 위치

- `clients/java/`

## 지원 범위

| 기능 | 플래그 | 설명 |
|------|--------|------|
| Chat Completions | 기본 | `POST /v1/chat/completions` |
| Responses API | `--api responses` | `POST /v1/responses` |
| Background 제출 | `--background` | 서버 측 비동기 큐잉 |
| Web 검색 | `--web-search` | `web_search_preview` tool 활성화 |
| 자동 Tool Calling | `--auto-tool-call` | deep_research 자동 개입 |
| 타임아웃 | `--timeout <초>` | 요청 대기 시간 (기본 30초) |
| Relay 모드 | `--target relay` | relay 서버 경유 호출 |
| Relay 스트림 | `--stream` | relay SSE 스트림 (`--target relay` 전용) |
| Deliverable 형식 | `--deliverable-format` | relay 호출 시 결과 형식 지정 |

## 테스트

```bash
cd clients/java
mvn test
```

## foreground chat/completions 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
```

## foreground responses 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
```

## background responses 제출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

이 경우 최종 텍스트 대신 원본 JSON 메타데이터를 반환합니다.

## 타임아웃 조정 (--timeout)

기본 타임아웃은 30초입니다. `o3-deep-research`처럼 응답 시간이 긴 모델을 사용할 때는 `--timeout <초>`로 늘리세요.

`--timeout`은 양의 정수 초만 허용합니다. 값이 없거나, 숫자가 아니거나, `0` 이하이면 Java CLI가 네트워크 호출 전에 즉시 명확한 오류 메시지와 함께 실패합니다.

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--timeout 300 짜장면의 역사를 상세히 조사해줘"
```

relay 호출에도 동일하게 적용됩니다:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 300 짜장면의 역사를 조사해줘"
```

## web_search_preview — 실시간 웹 검색 (--web-search)

`--web-search`는 `--api responses`와 함께 사용하면 모델이 실시간으로 웹을 검색합니다.

```bash
LITELLM_MODEL=gpt-4o \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api responses --web-search --timeout 60 짜장면이 처음 만들어진 연도를 한 줄로"
```

코드에서 직접 사용:

```java
LiteLlmClient client = new LiteLlmClient(baseUrl, apiKey, "gpt-4o");
String result = client.createResponse(
    "짜장면의 역사를 웹 검색으로 정리해줘",
    false,
    List.of(Map.of("type", "web_search_preview"))
);
System.out.println(result);
```

> **주의:** `--web-search`는 반드시 `--api responses`와 함께 사용해야 합니다.

## 자동 Tool Calling (--auto-tool-call)

`--auto-tool-call`은 OpenAI 표준 Responses API function calling을 사용해 모델이 스스로 `deep_research` 도구 호출 필요성을 판단하게 합니다.

표준 API surface는 `POST /v1/responses`이고, relay는 실제 tool 실행만 `POST /api/v1/tool-invocations`로 담당합니다.

```bash
# 터미널 A: relay 서버 시작
cd relay && uv run python -m litellm_relay

# 터미널 B: 자동 tool calling
LITELLM_MODEL=gpt-4o \
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--auto-tool-call --timeout 300 짜장면의 역사와 기원에 대해 상세히 조사해줘"
```

deep_research가 자동으로 호출됐을 때 stderr에 `[deep_research was called automatically]`와 함께 `response_id`, `previous_response_id`, `tool_call_id`, `invocation_id`, `invocation_token`, `upstream_response_id`가 출력됩니다.

코드에서 직접 사용:

```java
LiteLlmClient client = new LiteLlmClient(baseUrl, apiKey, "gpt-4o", Duration.ofSeconds(300));
LiteLlmClient.ToolCallingResult result = client.createResponseWithToolCalling(
    "짜장면의 역사와 기원에 대해 상세히 조사해줘",
    "http://127.0.0.1:8080"
);
System.out.println(result.finalText());
if (result.toolCalled()) {
    System.err.println("[deep_research가 자동으로 호출됐습니다]");
    System.err.println(result.responseId());
    System.err.println(result.invocationToken());
}
```

relay의 `GET /api/v1/tool-invocations/{invocation_id}`, `/wait`, `/events`를 직접 읽을 때는 `X-Invocation-Token: <invocation_token>` 헤더를 함께 보내야 합니다.

> **주의:** `--auto-tool-call`은 `--target relay`와 함께 쓸 수 없습니다.

## relay 호출 모드 (--target relay)

relay 서버가 실행 중일 때 `--target relay`로 relay를 경유해 호출할 수 있습니다.

```bash
# foreground
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay Summarize relay architecture"

# background
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --background Summarize relay architecture"

# stream (SSE)
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --stream Summarize relay architecture"
```

## deliverable 형식 지정 (--deliverable-format)

relay 호출 시 결과 형식을 지정할 수 있습니다.

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --deliverable-format markdown_report 짜장면의 역사"
```

지원 값: `markdown_brief` (기본값), `markdown_report`, `json_outline`

## relay invokeChat — /api/v1/chat 직접 호출 (비표준 helper)

Java에서 relay의 자동 orchestration helper 엔드포인트를 코드로 직접 호출할 수 있습니다. 다만 OpenAI 표준 auto tool calling 경로는 `POST /v1/responses`이며, 이 endpoint는 relay 예제 전용 convenience API입니다.

```java
import example.litellm.relay.RelayClient;
import java.time.Duration;

RelayClient client = new RelayClient("http://127.0.0.1:8080", Duration.ofSeconds(120));
RelayClient.ChatResult result = client.invokeChat("짜장면의 역사를 자세히 알려줘", true);
System.out.println(result.content());
if (result.toolCalled()) {
    System.out.println("[연구 도구 호출됨: " + result.toolName() + "]");
}
```

## 해석 포인트

- Java도 Python과 같은 API 흐름을 지원합니다.
- background 모드에서는 원본 JSON 메타데이터를 반환합니다.
- `--timeout`: 모델 응답 대기 시간 (초). 기본값 30초. 직접 호출과 relay 모두 지원
- `--web-search`: `gpt-4o` 계열에서 실시간 웹 검색 활성화
- `--auto-tool-call`: Responses API 표준 function calling 흐름 (relay 서버 필요)
- `--deliverable-format`: relay 호출 시 결과 형식 지정
- 현재 Java 예제 역시 상시 서비스가 아니라 1회성 CLI입니다.
- relay를 호출하려면 `--target relay`를 사용하고, 자세한 내용은 [Relay 중계 예제](relay-example.md)를 참고하세요.
