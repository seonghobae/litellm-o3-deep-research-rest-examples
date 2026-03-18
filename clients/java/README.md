## Java 직접 호출 예제

이 디렉터리에는 LiteLLM 호환 REST API의 OpenAI 호환 경로를 사용해
`o3-deep-research` 모델을 호출하는 Java 21 CLI 예제가 들어 있습니다.

지원 범위:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/responses` + `background: true`

설정은 환경 변수에서 읽고, 필요하면 `~/.env` 파일을 보조 입력으로 사용합니다.

- `LITELLM_API_KEY` — LiteLLM Proxy API 키
- `LITELLM_BASE_URL` — LiteLLM Proxy base URL
- `LITELLM_MODEL` (선택) — 기본값 `o3-deep-research`를 덮어씁니다

### 빠른 시작

```bash
cd clients/java
mvn test
```

실제 CLI 실행 예시:

```bash
cd clients/java
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Explain what o3-deep-research is useful for"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Explain what o3-deep-research is useful for"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Explain what o3-deep-research is useful for"
```

`--api responses --background`를 함께 사용하면, Java CLI도 Python과 동일하게 서버 측 background Responses 작업을 제출하고 `id`, `status` 같은 원본 JSON 메타데이터를 그대로 출력합니다.
