## LiteLLM o3-deep-research 예제 저장소

이 저장소는 LiteLLM Proxy를 통해 `o3-deep-research` 모델을 호출하는 세 가지 예제를 제공합니다.

1. `clients/python/` — Python 직접 호출 예제
2. `clients/java/` — Java 직접 호출 및 relay 호출 예제
3. `relay/` — LiteLLM Python SDK + FastAPI + Hypercorn 중계 예제

즉, 현재 `main` 기준으로 **직접 호출 2개 + 중계 예제 1개**가 모두 구현되어 있습니다.

## 필요한 환경 변수

### 직접 호출과 relay 서버가 공통으로 쓰는 값

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택, 기본값 `o3-deep-research`)

예시:

```dotenv
LITELLM_API_KEY=sk-your-lite-llm-api-key
LITELLM_BASE_URL=https://localhost:4000/v1
LITELLM_MODEL=o3-deep-research
```

direct Python/Java 예제는 `LITELLM_BASE_URL`을 `https://host:4000` 또는 `https://host:4000/v1` 형태로 받아 내부적으로 `/v1/` 루트로 정규화합니다. relay 예제는 같은 값을 LiteLLM SDK의 `api_base`로 넘기므로, upstream LiteLLM Proxy 기준으로 **root URL 또는 `/v1` URL을 그대로 사용할 수 있습니다.**

### relay 서버 전용 선택값

- `RELAY_HOST` (기본 `127.0.0.1`)
- `RELAY_PORT` (기본 `8080`)
- `RELAY_TIMEOUT_SECONDS` (기본 `30`)

### Java relay 호출 모드 전용 선택값

- `RELAY_BASE_URL` (기본 `http://127.0.0.1:8080`)

## 문서 사이트

이 저장소는 GitHub Pages로 한국어 문서를 출판합니다.

- 홈 문서: `docs/index.md`
- 통합 매뉴얼: `docs/ko/manual.md`
- relay 예제 안내: `docs/ko/relay-example.md`
- relay 구현 계획(보관): `docs/ko/relay-toolcalling-plan.md`

문서 URL:

- <https://seonghobae.github.io/litellm-o3-deep-research-rest-examples/>

## 빠른 시작

### Auto tool calling 기준

- canonical auto tool calling 경로는 OpenAI-compatible `POST /v1/responses` 입니다.
- Python/Java `--auto-tool-call`은 1차 `responses` 호출에서 `function_call`을 받고,
  relay `POST /api/v1/tool-invocations`로 실제 `deep_research`를 실행한 뒤,
  `previous_response_id` + `function_call_output`으로 2차 `responses` 호출을 완료합니다.
- relay의 `POST /api/v1/chat`은 예제 편의를 위한 helper endpoint이며,
  표준 OpenAI API surface 자체는 아닙니다.

### Python 직접 호출

```bash
cd clients/python
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_example "Reply with exactly: OK"
uv run python -m litellm_example --api responses "Reply with exactly: OK"
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
```

`o3-deep-research`처럼 응답 시간이 긴 모델을 사용할 때는 `--timeout`으로 대기 시간을 늘립니다.

```bash
uv run python -m litellm_example --timeout 300 "짜장면의 역사를 조사해줘"
```

### Java 직접 호출

```bash
cd clients/java
mvn test
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

긴 응답 시간이 예상될 때:

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--timeout 300 짜장면의 역사를 조사해줘"
```

### relay 서버 + Java relay 호출

터미널 A:

```bash
cd relay
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_relay
```

터미널 B:

```bash
cd clients/java
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay Summarize relay architecture"
```

relay 호출에도 `--timeout`을 적용할 수 있습니다:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 300 짜장면의 역사를 조사해줘"
```

stream 모드:

```bash
cd clients/java
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay --stream Summarize relay architecture"
```

## `background: true` 와 relay `--stream` 해석

- direct Python/Java CLI는 모두 **foreground 1회성 도구**입니다.
- direct `--background`는 **서버 측 Responses 작업을 background 모드로 제출**합니다.
- relay의 `--stream`은 Java가 relay의 `tool-invocations` 계약을 호출한 뒤, relay의 SSE 이벤트 스트림을 소비하는 흐름입니다.
- relay 외부 계약에서는 raw upstream `input`을 직접 노출하지 않고, `tool_name` + 구조화된 `arguments`만 사용합니다.

## 보안 주의

- 실제 `~/.env` 파일과 API 키는 Git에 커밋하지 마세요.
- 샘플 값이 필요하면 `.env.example`만 사용하세요.
- relay 오류 로그나 테스트 출력에 credential을 직접 노출하지 마세요.

## 문서 빌드 확인

```bash
python3 -m pip install -r requirements-docs.txt
mkdocs build --strict
```
