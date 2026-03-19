# LiteLLM o3-deep-research 한국어 매뉴얼

이 저장소는 `o3-deep-research` 모델을 LiteLLM 호환 방식으로 호출하는 **세 가지 예제**를 제공합니다.

1. `clients/python/` — Python 직접 호출 예제
2. `clients/java/` — Java 직접 호출 + relay 호출 예제
3. `relay/` — LiteLLM Python SDK + FastAPI + Hypercorn 중계 예제

직접 호출 예제는 OpenAI 호환 API 스타일인 다음 두 경로를 사용합니다.

- `POST /v1/chat/completions`
- `POST /v1/responses`

relay 예제는 raw `input` 문자열 대신 구조화된 **tool invocation 계약**을 사용합니다.

## 1. 저장소 개요

- Python 예제는 LiteLLM Proxy를 직접 호출합니다.
- Java 예제는 LiteLLM Proxy를 직접 호출할 수도 있고, relay를 호출할 수도 있습니다.
- relay 예제는 LiteLLM Python SDK를 내부에서 사용하고, FastAPI + Hypercorn으로 외부 API를 제공합니다.
- 테스트는 기본적으로 mock/local harness 중심이라서 실제 서버 없이도 돌아갑니다.
- 실제 LiteLLM Proxy가 있으면 direct/relay 둘 다 실호출 검증이 가능합니다.

## 2. 공통 사전 준비

다음 값이 필요합니다.

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택 사항, 기본값 `o3-deep-research`)

권장 방법은 홈 디렉터리의 `~/.env` 파일에 넣는 것입니다.

```dotenv
LITELLM_API_KEY=sk-your-lite-llm-api-key
LITELLM_BASE_URL=https://localhost:4000/v1
LITELLM_MODEL=o3-deep-research
```

### `LITELLM_BASE_URL` 규칙

다음 형태를 지원합니다.

- `https://localhost:4000`
- `https://localhost:4000/v1`

direct Python/Java 예제는 내부적으로 `/v1/` API 루트로 정규화해서 사용합니다. relay 예제는 `LITELLM_BASE_URL`을 LiteLLM SDK의 `api_base`로 그대로 넘기므로, upstream LiteLLM Proxy 기준으로 root URL 또는 `/v1` URL을 사용할 수 있습니다.

보안상 Python direct 예제는 원격 호스트에 대해 평문 `http://`를 허용하지 않습니다. 즉, 로컬 개발(`localhost`, `127.0.0.1`)이 아닌 경우에는 `https://`를 써야 합니다.

## 3. Python 직접 호출 예제

경로:

```bash
cd clients/python
```

### 의존성 설치 및 테스트

```bash
uv sync --all-extras --dev
uv run pytest
```

### chat/completions 호출

```bash
uv run python -m litellm_example "Reply with exactly: OK"
```

### responses 호출

```bash
uv run python -m litellm_example --api responses "Reply with exactly: OK"
```

### responses background 제출

```bash
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
```

이 경우 최종 텍스트 대신 `id`, `status` 같은 후속 추적용 메타데이터가 담긴 원본 JSON을 출력합니다.

## 4. Java 예제

경로:

```bash
cd clients/java
```

### 빌드 및 테스트

```bash
mvn test
```

### 4-1. direct chat/completions 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
```

### 4-2. direct responses 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
```

### 4-3. direct responses background 제출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

### 4-4. relay 호출 모드

relay 서버가 이미 떠 있다고 가정하면 다음처럼 Java에서 relay를 호출할 수 있습니다.

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay Summarize relay architecture"
```

background 제출:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay --background Summarize relay architecture"
```

stream:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay --stream Summarize relay architecture"
```

## 5. relay 중계 예제

경로:

```bash
cd relay
```

### relay 전용 설정

relay는 공통 upstream 설정 외에도 다음 값을 쓸 수 있습니다.

- `RELAY_HOST` (기본 `127.0.0.1`)
- `RELAY_PORT` (기본 `8080`)
- `RELAY_TIMEOUT_SECONDS` (기본 `30`)

### 실행

```bash
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_relay
```

### 공개 API

- `POST /api/v1/tool-invocations`
- `GET /api/v1/tool-invocations/{invocation_id}`
- `GET /api/v1/tool-invocations/{invocation_id}/wait`
- `GET /api/v1/tool-invocations/{invocation_id}/events`

### 공개 계약 예시

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

relay 내부에서만 위 구조를 LiteLLM Responses 요청으로 변환하며, 내부 모델 이름은 `litellm_proxy/<model>` 형태를 사용합니다.

## 6. `background` 와 `stream` 해석

### 6-1. direct 예제의 `background`

- direct Python/Java CLI는 foreground 1회성 프로세스입니다.
- `--background`는 로컬 프로세스를 daemon으로 바꾸는 것이 아니라, 서버 측 Responses 작업을 background 모드로 제출하는 것입니다.

### 6-2. relay 예제의 `stream`

- relay는 `POST /api/v1/tool-invocations`로 invocation을 만들고,
- `GET /api/v1/tool-invocations/{invocation_id}/events`로 `text/event-stream`을 제공합니다.
- 현재 구현은 text delta만 중계하는 **text-focused SSE 예제**입니다.

## 7. 문제 해결

### `LITELLM_API_KEY is not set`

- 환경변수가 없거나
- `~/.env` 파일이 없거나
- 값이 비어 있을 수 있습니다.

확인:

```bash
echo "$LITELLM_API_KEY"
cat ~/.env
```

### `LITELLM_BASE_URL is not set`

예시:

```dotenv
LITELLM_BASE_URL=https://your-litellm-host/v1
```

### `RELAY_BASE_URL` 오류

Java relay 모드는 `RELAY_BASE_URL`이 없으면 기본값 `http://127.0.0.1:8080`을 사용합니다. 다른 주소를 쓰고 있다면 환경변수를 맞춰야 합니다.

### SSL / 인증서 오류

Python direct 예제는 `certifi` CA 번들을 사용합니다. 그래도 실패하면:

- LiteLLM Proxy 인증서 체인이 정상인지 확인
- 사설 인증서라면 신뢰 저장소 구성이 필요한지 확인

### 4xx / 5xx 응답

점검 항목:

- API 키가 맞는지
- 모델 이름(`o3-deep-research`)이 실제 LiteLLM 설정에서 허용되는지
- 프록시가 `/v1/chat/completions` 또는 `/v1/responses`를 노출하는지
- relay라면 upstream Proxy와 relay의 listen 주소가 모두 맞는지

## 8. 요약

- direct Python/Java 예제는 OpenAI 호환 `chat/completions`, `responses`, `background: true`를 지원합니다.
- relay 예제는 LiteLLM Python SDK + FastAPI + Hypercorn으로 구현되어 있습니다.
- Java는 `--target relay` 모드로 relay를 호출할 수 있습니다.
- relay 외부 계약은 `tool_name` + 구조화된 `arguments` 중심이며, raw upstream `input`은 내부에만 존재합니다.
- 문서 사이트는 GitHub Pages에서 한국어로 출판됩니다.
