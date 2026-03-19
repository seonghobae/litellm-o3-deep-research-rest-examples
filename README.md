## LiteLLM o3-deep-research 예제 저장소

이 저장소는 LiteLLM Proxy를 통해 `o3-deep-research`와 `gpt-4o` 계열 모델을 호출하는 세 가지 예제를 제공합니다.

1. `clients/python/` — Python 직접 호출 예제
2. `clients/java/` — Java 직접 호출 및 relay 호출 예제
3. `relay/` — LiteLLM Python SDK + FastAPI + Hypercorn 중계 예제

현재 `main` 기준으로 다음 기능이 모두 구현되어 있습니다.

- direct Python / Java: `chat/completions`, `responses`, `background: true`, `--timeout`
- direct Python / Java: `--web-search`, `--auto-tool-call`
- relay: 구조화된 `tool-invocations` 계약, `wait`, `events` SSE, `POST /api/v1/chat`
- relay deep research contract: `system_prompt`, `text_format`, `deliverable_format`
- relay chat contract: `system_prompt`, `deliverable_format`, structured `ChatResponse`

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
- `RELAY_TIMEOUT_SECONDS` (기본 `30`) — Chat Completions orchestration timeout
- `RELAY_RESEARCH_TIMEOUT_SECONDS` (기본 `300`) — deep_research 실행 timeout
- `LITELLM_CHAT_MODEL` (기본 `gpt-4o`) — `POST /api/v1/chat` orchestration 모델

`LITELLM_MODEL`은 실제 deep research 실행 모델(`o3-deep-research` 기본값)이고,
`LITELLM_CHAT_MODEL`은 function calling을 수행하는 chat orchestration 모델입니다.

### Java relay 호출 모드 전용 선택값

- `RELAY_BASE_URL` (기본 `http://127.0.0.1:8080`)

## 문서 사이트

이 저장소는 GitHub Pages로 한국어 문서를 출판합니다.

- 홈 문서: `docs/index.md`
- 통합 매뉴얼: `docs/ko/manual.md`
- 시작 가이드: `docs/ko/quickstart.md`
- relay 예제 안내: `docs/ko/relay-example.md`
- 자동 tool calling 가이드: `docs/ko/auto-toolcalling.md`
- relay 구현 계획(보관): `docs/ko/relay-toolcalling-plan.md`

문서 URL:

- <https://seonghobae.github.io/litellm-o3-deep-research-rest-examples/>

## 빠른 시작

### Python 직접 호출

```bash
cd clients/python
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_example "Reply with exactly: OK"
uv run python -m litellm_example --api responses "Reply with exactly: OK"
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
LITELLM_MODEL=gpt-4o uv run python -m litellm_example --api responses --web-search "짜장면의 역사를 웹 검색으로 정리해줘"
```

`o3-deep-research`처럼 응답 시간이 긴 모델을 사용할 때는 `--timeout`으로 대기 시간을 늘립니다.

```bash
uv run python -m litellm_example --timeout 300 "짜장면의 역사를 조사해줘"
```

relay와 함께 자동 tool calling을 쓰려면:

```bash
# 터미널 A
cd relay
uv run python -m litellm_relay

# 터미널 B
cd clients/python
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example --auto-tool-call --timeout 300 "짜장면의 역사와 기원을 자세히 조사해줘"
```

### Java 직접 호출

```bash
cd clients/java
mvn test
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
LITELLM_MODEL=gpt-4o mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --web-search 짜장면의 역사를 웹 검색으로 정리해줘"
```

긴 응답 시간이 예상될 때:

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--timeout 300 짜장면의 역사를 조사해줘"
```

relay와 함께 자동 tool calling을 쓰려면:

```bash
# 터미널 A
cd relay
uv run python -m litellm_relay

# 터미널 B
cd clients/java
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--auto-tool-call --timeout 300 짜장면의 역사와 기원을 자세히 조사해줘"
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

relay-side 자동 orchestration (`POST /api/v1/chat`) 예시:

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사와 기원을 자세히 알려줘",
    "auto_tool_call": true,
    "system_prompt": "Always answer in English only.",
    "deliverable_format": "markdown_report"
  }'
```

## `background: true` 와 relay `--stream` 해석

- direct Python/Java CLI는 모두 **foreground 1회성 도구**입니다.
- direct `--background`는 **서버 측 Responses 작업을 background 모드로 제출**합니다.
- relay의 `--stream`은 Java가 relay의 `tool-invocations` 계약을 호출한 뒤, relay의 SSE 이벤트 스트림을 소비하는 흐름입니다.
- relay 외부 계약에서는 raw upstream `input`을 직접 노출하지 않고, `tool_name` + 구조화된 `arguments`만 사용합니다.

## 핵심 기능 빠른 요약

### `web_search_preview`

- Python / Java direct client에서 `--api responses --web-search`로 사용합니다.
- 일반 모델(`gpt-4o`)에 실시간 웹 검색을 부여할 때 유용합니다.
- `o3-deep-research` 자체 경로와는 별개 기능입니다.

### 자동 Tool Calling

- direct Python / Java의 `--auto-tool-call`은 Chat Completions function calling을 사용합니다.
- 모델이 `deep_research`가 필요하다고 판단하면 relay를 자동 호출합니다.
- relay 자체도 `POST /api/v1/chat`으로 동일 개념의 server-side orchestration을 제공합니다.

### `system_prompt` 와 `text_format`

- relay `deep_research` wrapper는 `system_prompt`를 Responses API `instructions` 필드로 전달합니다.
- relay `deep_research` wrapper는 `text_format`을 Responses API `text.format`으로 전달합니다.
- `json_schema`는 `gpt-4o` 계열에서 지원되며, `o3-deep-research`는 지원하지 않습니다.

## Relay `/api/v1/chat` 계약 요약

요청 필드:

- `message`
- `context`
- `auto_tool_call`
- `system_prompt`
- `deliverable_format`

응답 필드:

- `content`
- `tool_called`
- `tool_name`
- `research_summary`

upstream deep research 단계에서 오류가 나도 bare HTTP 500 대신 구조화된 `ChatResponse`를 반환합니다.

## 라이브 검증 범위

현재 저장소는 문서와 acceptance criteria 기준으로 다음 경로들을 라이브 검증 대상으로 관리합니다.

- Python direct `chat` / `responses` / `background`
- Java direct `chat` / `responses` / `background`
- relay `tool-invocations` foreground / background / stream
- relay `POST /api/v1/chat` no-tool / tool-called
- Python / Java `--web-search`
- Python / Java `--auto-tool-call`
- relay `/api/v1/chat`의 `system_prompt`, `deliverable_format`

실제 예시와 세부 결과는 `docs/ko/manual.md`와 `docs/ko/auto-toolcalling.md`를 참고하세요.

## 보안 주의

- 실제 `~/.env` 파일과 API 키는 Git에 커밋하지 마세요.
- 샘플 값이 필요하면 `.env.example`만 사용하세요.
- relay 오류 로그나 테스트 출력에 credential을 직접 노출하지 마세요.

## 문서 빌드 확인

```bash
python3 -m pip install -r requirements-docs.txt
mkdocs build --strict
```
