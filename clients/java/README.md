# Java 예제

이 디렉터리에는 LiteLLM 호환 REST API를 직접 호출하는 Java 21 CLI와,
relay를 호출하는 Java 모드가 함께 들어 있습니다.

지원 범위:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/responses` + `background: true`
- `POST /v1/responses` + `web_search_preview`
- OpenAI 표준 Responses API function calling 기반 `--auto-tool-call`
- `POST /api/v1/tool-invocations` via relay mode
- `GET /api/v1/tool-invocations/{id}/events` via relay stream mode

추가 플래그:

- `--timeout`
- `--deliverable-format`
- `--target relay`
- `--stream`

설정은 환경 변수에서 읽고, 필요하면 `~/.env` 파일을 보조 입력으로 사용합니다.

- `LITELLM_API_KEY` — LiteLLM Proxy API 키
- `LITELLM_BASE_URL` — LiteLLM Proxy base URL
- `LITELLM_MODEL` (선택) — 기본값 `o3-deep-research`를 덮어씁니다
- `RELAY_BASE_URL` (선택) — relay mode 및 `--auto-tool-call`에서 relay 실행 주소

## 설치 / 빌드

```bash
cd clients/java
mvn test
```

릴리스 아티팩트 생성:

```bash
cd clients/java
mvn -DskipTests package
```

산출물 예시:

- `target/litellm-o3-deep-research-java-0.1.0.jar`

### 빠른 시작

```bash
cd clients/java
```

direct 호출 예시:

```bash
cd clients/java
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Explain what o3-deep-research is useful for"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Explain what o3-deep-research is useful for"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Explain what o3-deep-research is useful for"
LITELLM_MODEL=gpt-4o mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --web-search 짜장면의 역사를 웹 검색으로 정리해줘"
```

`--api responses --background`를 함께 사용하면, Java CLI도 Python과 동일하게 서버 측 background Responses 작업을 제출하고 `id`, `status` 같은 원본 JSON 메타데이터를 그대로 출력합니다.

relay 호출 예시:

```bash
cd clients/java
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay Summarize relay architecture"

RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay --stream Summarize relay architecture"
```

## 자동 Tool Calling (`--auto-tool-call`)

이 경로는 OpenAI 표준 Responses API function calling 패턴을 사용합니다.

1. `POST /v1/responses` + `tools=[deep_research]`
2. 응답 `output`에서 `function_call` 감지
3. relay `POST /api/v1/tool-invocations`로 실제 deep research 실행
4. `previous_response_id` + `function_call_output`로 두 번째 `POST /v1/responses`

```bash
# 터미널 A
cd relay
uv run python -m litellm_relay

# 터미널 B
cd clients/java
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--auto-tool-call --timeout 300 짜장면의 역사와 기원을 자세히 조사해줘"
```

도구가 실제로 호출되면 stderr에 다음 key들이 함께 출력됩니다.

- `response_id`
- `previous_response_id`
- `tool_call_id`
- `invocation_id`
- `invocation_token`
- `upstream_response_id`

relay의 `GET /api/v1/tool-invocations/{invocation_id}`, `/wait`, `/events`를 읽을 때는 `X-Invocation-Token: <invocation_token>` 헤더를 함께 보내야 합니다.
