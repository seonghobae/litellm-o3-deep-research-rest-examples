## Python 직접 호출 예제

이 디렉터리에는 LiteLLM 호환 REST API의 OpenAI 호환 경로를 사용해
`o3-deep-research` 모델을 호출하는 작은 Python CLI 예제가 들어 있습니다.

지원 범위:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/responses` + `background: true`

설정은 환경 변수에서 읽고, 필요하면 `~/.env` 파일을 보조 입력으로 사용합니다.

- `LITELLM_API_KEY` — LiteLLM Proxy API 키
- `LITELLM_BASE_URL` — LiteLLM Proxy base URL (`https://localhost:4000` 또는 `https://localhost:4000/v1`)
- `LITELLM_MODEL` (선택) — 기본값 `o3-deep-research`를 덮어씁니다

### 빠른 시작

```bash
cd clients/python
uv sync --all-extras --dev
uv run pytest
```

실제 CLI 실행 예시:

```bash
cd clients/python
uv run python -m litellm_example "Summarize the purpose of the o3-deep-research model."
uv run python -m litellm_example --api responses "Summarize the purpose of the o3-deep-research model."
uv run python -m litellm_example --api responses --background "Summarize the purpose of the o3-deep-research model."
```

`--api responses --background`를 함께 사용하면, 클라이언트가 daemon으로 바뀌는 것이 아니라 서버 측 Responses 작업을 background 모드로 제출합니다. 이때 CLI는 최종 텍스트 대신 `id`, `status` 등을 포함한 원본 JSON 메타데이터를 그대로 출력합니다.
