## Python 직접 호출 예제

이 디렉터리에는 LiteLLM 호환 REST API의 OpenAI 호환 경로를 사용해
`o3-deep-research` 모델을 호출하는 작은 Python CLI 예제가 들어 있습니다.

지원 범위:

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/responses` + `background: true`
- `POST /v1/responses` + `web_search_preview`
- OpenAI 표준 Responses API function calling 기반 `--auto-tool-call`
- `--timeout <초>`로 long-running 모델 대기 시간 조정

설정은 환경 변수에서 읽고, 필요하면 `~/.env` 파일을 보조 입력으로 사용합니다.

- `LITELLM_API_KEY` — LiteLLM Proxy API 키
- `LITELLM_BASE_URL` — LiteLLM Proxy base URL (`https://localhost:4000` 또는 `https://localhost:4000/v1`)
- `LITELLM_MODEL` (선택) — 기본값 `o3-deep-research`를 덮어씁니다
- `RELAY_BASE_URL` (선택) — `--auto-tool-call` 시 relay `tool-invocations` 실행 주소

## 설치

개발용 체크아웃 기준:

```bash
cd clients/python
uv sync --all-extras --dev
```

editable install 기준:

```bash
cd clients/python
uv pip install -e .
```

배포 아티팩트 기준:

```bash
cd clients/python
uv run --with build python -m build
pip install dist/litellm_o3_deep_research_python-0.1.0-py3-none-any.whl
```

### 빠른 시작

```bash
cd clients/python
uv run pytest
```

실제 CLI 실행 예시:

```bash
cd clients/python
uv run python -m litellm_example "Summarize the purpose of the o3-deep-research model."
uv run python -m litellm_example --api responses "Summarize the purpose of the o3-deep-research model."
uv run python -m litellm_example --api responses --background "Summarize the purpose of the o3-deep-research model."
LITELLM_MODEL=gpt-4o uv run python -m litellm_example --api responses --web-search "짜장면의 역사를 웹 검색으로 정리해줘"
```

`--api responses --background`를 함께 사용하면, 클라이언트가 daemon으로 바뀌는 것이 아니라 서버 측 Responses 작업을 background 모드로 제출합니다. 이때 CLI는 최종 텍스트 대신 `id`, `status` 등을 포함한 원본 JSON 메타데이터를 그대로 출력합니다.

## 자동 Tool Calling (`--auto-tool-call`)

이 경로는 더 이상 relay `POST /api/v1/chat`에 의존하지 않고, OpenAI 표준 Responses API function calling 패턴을 사용합니다.

1. `POST /v1/responses` + `tools=[deep_research]`
2. 응답 `output`에서 `function_call` 감지
3. relay `POST /api/v1/tool-invocations`로 실제 deep research 실행
4. `previous_response_id` + `function_call_output`로 두 번째 `POST /v1/responses`

```bash
# 터미널 A
cd relay
uv run python -m litellm_relay

# 터미널 B
cd clients/python
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example --auto-tool-call --timeout 300 "짜장면의 역사와 기원을 자세히 조사해줘"
```

도구가 실제로 호출되면 stderr에 다음 key들이 함께 출력됩니다.

- `response_id`
- `previous_response_id`
- `tool_call_id`
- `invocation_id`
- `upstream_response_id`

## 패키지 빌드 검증

```bash
cd clients/python
uv run --with build python -m build
```

산출물:

- `dist/*.whl`
- `dist/*.tar.gz`
