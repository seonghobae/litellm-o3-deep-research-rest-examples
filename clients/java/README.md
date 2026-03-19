# Java 예제

이 디렉터리에는 LiteLLM 호환 REST API를 직접 호출하는 Java 21 CLI와,
relay를 호출하는 Java 모드가 함께 들어 있습니다.

지원 범위:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/responses` + `background: true`
- `POST /api/v1/tool-invocations` via relay mode
- `GET /api/v1/tool-invocations/{id}/events` via relay stream mode

설정은 환경 변수에서 읽고, 필요하면 `~/.env` 파일을 보조 입력으로 사용합니다.

- `LITELLM_API_KEY` — LiteLLM Proxy API 키
- `LITELLM_BASE_URL` — LiteLLM Proxy base URL
- `LITELLM_MODEL` (선택) — 기본값 `o3-deep-research`를 덮어씁니다

### 빠른 시작

```bash
cd clients/java
mvn test
```

direct 호출 예시:

```bash
cd clients/java
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Explain what o3-deep-research is useful for"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Explain what o3-deep-research is useful for"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Explain what o3-deep-research is useful for"
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
