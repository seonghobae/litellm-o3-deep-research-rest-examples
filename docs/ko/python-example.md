# Python 직접 호출 예제

## 위치

- `clients/python/`

## 지원 범위

| 기능 | 플래그 | 설명 |
|------|--------|------|
| Chat Completions | 기본 | `POST /v1/chat/completions` |
| Responses API | `--api responses` | `POST /v1/responses` |
| Background 제출 | `--background` | 서버 측 비동기 큐잉 |
| Web 검색 | `--web-search` | `web_search_preview` tool 활성화 |
| 자동 Tool Calling | `--auto-tool-call` | deep_research 자동 개입 |
| 타임아웃 | `--timeout <초>` | 요청 대기 시간 (기본 30초) |

## 테스트

```bash
cd clients/python
uv run pytest
```

## foreground chat/completions 호출

```bash
uv run python -m litellm_example "Reply with exactly: OK"
```

## foreground responses 호출

```bash
uv run python -m litellm_example --api responses "Reply with exactly: OK"
```

## background responses 제출

```bash
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
```

이 경우 최종 텍스트 대신 `id`, `status` 같은 후속 추적용 메타데이터가 담긴 원본 JSON을 출력합니다.

## 타임아웃 조정 (--timeout)

기본 타임아웃은 30초입니다. `o3-deep-research`처럼 응답 시간이 긴 모델을 사용할 때는 `--timeout <초>`로 늘리세요.

```bash
uv run python -m litellm_example --timeout 300 "짜장면의 역사를 상세히 조사해줘"
uv run python -m litellm_example --api responses --timeout 300 "짜장면의 역사를 상세히 조사해줘"
```

## web_search_preview — 실시간 웹 검색 (--web-search)

`--web-search`는 `--api responses`와 함께 사용하면 모델이 실시간으로 웹을 검색해서 최신 정보를 답변에 반영합니다. `gpt-4o` 같은 일반 모델에도 검색 능력을 부여합니다.

```bash
LITELLM_MODEL=gpt-4o \
uv run python -m litellm_example \
  --api responses \
  --web-search \
  --timeout 60 \
  "짜장면이 처음 만들어진 연도를 한 줄로"
```

**실제 결과 예시:**

```
짜장면은 1905년에 중국 청나라 출신 화교들에 의해 인천 차이나타운에서 처음 만들어졌습니다.
```

코드에서 직접 사용:

```python
from litellm_example.client import LiteLLMClient

client = LiteLLMClient(base_url, api_key, model="gpt-4o")
result = client.create_response(
    "짜장면의 역사를 웹 검색으로 정리해줘",
    tools=[{"type": "web_search_preview"}],
)
print(result)
```

> **주의:** `--web-search`는 반드시 `--api responses`와 함께 사용해야 합니다. `--api chat`에는 적용되지 않습니다.

## 자동 Tool Calling (--auto-tool-call)

`--auto-tool-call`은 모델이 스스로 `deep_research` 도구 호출 필요성을 판단하게 합니다.
- 단순 질문 → 모델이 직접 답변
- 심층 조사가 필요한 질문 → relay를 통해 deep_research 자동 실행 → 최종 답변 합성

이 플래그는 relay 서버(`RELAY_BASE_URL`)가 실행 중이어야 합니다.
표준 API surface는 `POST /v1/responses`이고, relay는 실제 tool 실행만 `POST /api/v1/tool-invocations`로 담당합니다.

```bash
# 터미널 A: relay 서버 시작
cd relay && uv run python -m litellm_relay

# 터미널 B: 자동 tool calling
LITELLM_MODEL=gpt-4o \
RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example \
  --auto-tool-call \
  --timeout 300 \
  "짜장면의 역사와 기원에 대해 상세히 조사해줘"
```

deep_research가 자동으로 호출됐을 때 stderr에 `[deep_research was called automatically]`가 출력됩니다.

**실제 결과:**

- stderr: `[deep_research was called automatically]`
- stdout: BTS 또는 짜장면 역사에 대한 구조화된 마크다운 보고서

> **주의:** `--auto-tool-call`은 `--target relay`와 함께 쓸 수 없습니다.

코드에서 직접 사용:

```python
from litellm_example.client import LiteLLMClient

client = LiteLLMClient(base_url, api_key, model="gpt-4o")
answer, tool_called = client.create_chat_with_tool_calling(
    "짜장면의 역사와 기원에 대해 상세히 조사해줘",
    relay_base_url="http://127.0.0.1:8080",
)
print(answer)
if tool_called:
    print("[deep_research가 자동으로 호출됐습니다]", file=sys.stderr)
```

## 해석 포인트

- foreground 호출: 바로 읽을 수 있는 텍스트를 반환
- background 호출: `id`, `status` 같은 메타데이터 중심 응답 (후속 폴링 필요)
- `--timeout`: 모델 응답 대기 시간 (초). 기본값 30초
- `--web-search`: `gpt-4o` 계열에서 실시간 웹 검색 활성화 (`o3-deep-research`는 자체적으로 조사하므로 불필요)
- `--auto-tool-call`: Responses API function-calling 2-step 흐름 (1차 `responses` → `function_call` 감지 → relay `tool-invocations` 실행 → 2차 `responses` with `function_call_output`)
- 현재 Python 예제는 상시 실행 서버가 아니라 1회성 CLI입니다.
