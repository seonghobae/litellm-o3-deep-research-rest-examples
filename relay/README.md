## Relay 중계 예제

이 디렉터리는 LiteLLM Python SDK를 감싼 **FastAPI + Hypercorn relay 예제**입니다.

relay의 목적은 Java가 upstream LiteLLM Proxy를 직접 호출하는 대신, 다음과 같은 **구조화된 tool invocation 계약**을 사용하게 만드는 것입니다.

- `tool_name`
- `arguments.research_question`
- `arguments.context`
- `arguments.constraints`
- `arguments.deliverable_format`
- `arguments.background`
- `arguments.stream`

relay 내부에서만 위 구조를 LiteLLM Responses API 호출로 번역합니다.

## 환경 변수

공통 upstream 설정:

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택, 기본 `o3-deep-research`)

relay 런타임 설정:

- `RELAY_HOST` (기본 `127.0.0.1`)
- `RELAY_PORT` (기본 `8080`)
- `RELAY_TIMEOUT_SECONDS` (기본 `30`)

`LITELLM_BASE_URL`은 relay 내부에서 LiteLLM SDK의 `api_base`로 그대로 전달됩니다. 따라서 upstream LiteLLM Proxy가 허용하는 root URL 또는 `/v1` URL을 사용할 수 있습니다.

## 실행

```bash
cd relay
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_relay
```

기본 listen 주소:

- `http://127.0.0.1:8080`

## 공개 API

- `POST /api/v1/tool-invocations`
- `GET /api/v1/tool-invocations/{invocation_id}`
- `GET /api/v1/tool-invocations/{invocation_id}/wait`
- `GET /api/v1/tool-invocations/{invocation_id}/events`

## Java에서 relay 호출

```bash
cd clients/java
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay Summarize relay architecture"
```

## 구현 범위

- structured request → LiteLLM Responses request 매핑
- background status polling
- text-only SSE streaming
- direct clients와 분리된 Java relay mode
