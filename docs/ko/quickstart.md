# 시작하기

## 1. 필요한 값

다음 환경 변수가 필요합니다.

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택, 기본값 `o3-deep-research`)

권장 방식은 홈 디렉터리의 `~/.env` 파일입니다.

```dotenv
LITELLM_API_KEY=sk-your-lite-llm-api-key
LITELLM_BASE_URL=https://localhost:4000/v1
LITELLM_MODEL=o3-deep-research
```

## 2. Python 예제 시작

```bash
cd clients/python
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_example "Reply with exactly: OK"
```

`o3-deep-research`처럼 응답이 느린 모델을 직접 호출할 때는 `--timeout`(초 단위)을 늘리세요.

```bash
uv run python -m litellm_example --timeout 300 "짜장면의 역사를 조사해줘"
```

## 3. Java 예제 시작

```bash
cd clients/java
mvn test
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
```

긴 응답 시간이 예상될 때:

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--timeout 300 짜장면의 역사를 조사해줘"
```

## 4. Relay 예제 시작

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

relay 호출도 `--timeout`을 지원합니다:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 300 짜장면의 역사를 조사해줘"
```

## 5. base URL 규칙

다음 두 형태를 지원합니다.

- `https://localhost:4000`
- `https://localhost:4000/v1`

direct Python/Java 예제는 내부적으로 `/v1/` 루트로 정규화합니다. relay 예제는 같은 값을 LiteLLM SDK의 `api_base`로 그대로 사용하므로, upstream LiteLLM Proxy가 허용하는 root URL 또는 `/v1` URL을 넣으면 됩니다.

## 6. 구현된 기능 전체 목록

### 직접 호출 클라이언트 (Python / Java)

| 기능 | Python | Java | 플래그 |
|------|--------|------|--------|
| Chat Completions | ✅ | ✅ | 기본값 |
| Responses API | ✅ | ✅ | `--api responses` |
| Background 제출 | ✅ | ✅ | `--background` |
| 타임아웃 조정 | ✅ | ✅ | `--timeout <초>` |
| Web 검색 | ✅ | ✅ | `--web-search` (requires `--api responses`) |
| 자동 Tool Calling | ✅ | ✅ | `--auto-tool-call` (relay 서버 필요) |

### Relay 서버 (FastAPI + Hypercorn)

| 기능 | 엔드포인트 / 환경변수 |
|------|---------------------|
| 구조화된 tool invocation | `POST /api/v1/tool-invocations` |
| 상태 조회 | `GET /api/v1/tool-invocations/{id}` |
| 동기 대기 | `GET /api/v1/tool-invocations/{id}/wait` |
| SSE 스트리밍 | `GET /api/v1/tool-invocations/{id}/events` |
| 자동 tool calling chat | `POST /api/v1/chat` |
| System prompt | `arguments.system_prompt` |
| JSON 강제 출력 | `arguments.text_format` |
| Background 제출 | `arguments.background: true` |

### Relay 환경변수

| 변수 | 기본값 | 설명 |
|------|--------|------|
| `RELAY_HOST` | `127.0.0.1` | 서버 바인딩 주소 |
| `RELAY_PORT` | `8080` | 서버 포트 |
| `RELAY_TIMEOUT_SECONDS` | `30` | Chat Completions 타임아웃 |
| `RELAY_RESEARCH_TIMEOUT_SECONDS` | `300` | deep_research 실행 타임아웃 |
| `LITELLM_CHAT_MODEL` | `gpt-4o` | auto tool calling orchestration 모델 |

### Java relay 클라이언트 모드

```bash
# foreground
RELAY_BASE_URL=http://127.0.0.1:8080 mvn -q exec:java ... -Dexec.args="--target relay ..."

# background
... -Dexec.args="--target relay --background ..."

# stream
... -Dexec.args="--target relay --stream ..."

# auto tool calling (relay-side orchestration)
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 mvn -q exec:java ... -Dexec.args="--auto-tool-call ..."
```
