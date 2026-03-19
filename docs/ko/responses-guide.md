# Responses / Background / Web 검색 / 자동 Tool Calling 가이드

## 1. `responses` 와 `chat/completions` 차이

| | `chat/completions` | `responses` |
|-|-------------------|-------------|
| 입력 형식 | `messages` 배열 | `input` 문자열 |
| background 지원 | ❌ | ✅ (`background: true`) |
| web_search tool | ❌ | ✅ |
| output_text 추출 | `choices[0].message.content` | `output_text` 또는 `output[].content[].text` |
| o3-deep-research 권장 | 제한적 | ✅ (공식 지원) |

현재 저장소는 두 방식을 모두 예제로 제공합니다.

## 2. `background: true` 의 의미

`background: true` 는 **서버 측 작업 제출 방식**입니다.

즉:

- 로컬 프로세스가 background daemon이 된다는 뜻이 아님
- 서버가 작업을 큐잉/비동기 처리할 수 있게 요청한다는 뜻

반환값: `id`, `status` 같은 메타데이터 (최종 텍스트가 아님)

```bash
# Python
uv run python -m litellm_example --api responses --background "조사 요청"

# Java
mvn -q exec:java ... -Dexec.args="--api responses --background 조사 요청"
```

## 3. 직접 예제와 relay 예제의 background 비교

| | direct Python/Java | relay |
|-|-------------------|-------|
| 실행 방식 | 1회성 CLI 프로세스 | FastAPI + Hypercorn 장기 서버 |
| background 의미 | 서버 측 비동기 큐잉 | 동일 |
| background 결과 | 원본 JSON 메타데이터 출력 | `upstream_response_id`, `status` 반환 |
| 후속 폴링 | 직접 구현 필요 | `GET /api/v1/tool-invocations/{id}/wait` |
| SSE 스트리밍 | 미지원 | `GET /api/v1/tool-invocations/{id}/events` |

## 4. web_search_preview — 일반 모델에 웹 검색 추가

`web_search_preview`는 Responses API의 내장 tool입니다. `gpt-4o` 같은 일반 모델에 실시간 웹 검색 능력을 부여합니다.

```
요청: POST /v1/responses
{
  "model": "gpt-4o",
  "input": "짜장면의 역사를 웹 검색으로 정리해줘",
  "tools": [{"type": "web_search_preview"}]
}
```

CLI 사용:

```bash
# Python
LITELLM_MODEL=gpt-4o \
uv run python -m litellm_example \
  --api responses --web-search --timeout 60 \
  "짜장면의 역사를 웹 검색으로 3문단 정리해줘"

# Java
LITELLM_MODEL=gpt-4o \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api responses --web-search --timeout 60 짜장면의 역사를 웹 검색으로 정리해줘"
```

> `o3-deep-research`는 자체적으로 심층 조사를 수행하므로 `--web-search`가 불필요합니다. `gpt-4o` 같은 범용 모델에 최신 정보가 필요할 때 유용합니다.

**실제 결과 예시 (gpt-4o + web_search_preview):**

```
짜장면은 1905년에 중국 청나라 출신 화교들에 의해 인천 차이나타운에서 처음 만들어졌습니다.
[출처: 코리아타임즈]
```

## 5. 자동 Tool Calling — 모델이 deep_research 여부를 스스로 결정

### 5-1. 개념

기존 방식은 항상 명시적으로 deep_research를 호출해야 했습니다. 자동 tool calling은 모델이 스스로 "이 질문은 심층 조사가 필요하다"고 판단해서 deep_research를 자동으로 실행합니다.

```
사용자: "짜장면의 역사를 자세히 알려줘"
         ↓
모델: "이 질문은 deep_research가 필요하다"
         ↓
deep_research 자동 실행 (o3-deep-research)
         ↓
모델이 연구 결과로 최종 자연어 답변 합성
```

### 5-2. Client-Side (--auto-tool-call)

직접 클라이언트에서 3-turn function calling 흐름을 구현합니다.

```bash
# relay 서버 먼저 시작
cd relay && uv run python -m litellm_relay

# Python
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example --auto-tool-call --timeout 300 \
  "짜장면의 역사와 기원에 대해 상세히 조사해줘"

# Java
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--auto-tool-call --timeout 300 짜장면의 역사와 기원에 대해 상세히 조사해줘"
```

### 5-3. Relay-Side (POST /api/v1/chat)

relay가 모든 orchestration을 내부에서 처리합니다. 클라이언트는 단순 chat 메시지만 보내면 됩니다.

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사와 기원에 대해 상세히 조사해줘",
    "auto_tool_call": true
  }'
```

**응답 예시 (deep_research 호출됨):**
```json
{
  "content": "짜장면은 중국에서 유래된 자장몐(炸酱面)을 바탕으로...",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "# 짜장면의 역사와 기원에 관한 상세 연구\n..."
}
```

자세한 내용은 [자동 Tool Calling 가이드](auto-toolcalling.md)를 참고하세요.

## 6. relay 스트리밍

relay 예제는 다음 lifecycle을 정식으로 다룹니다.

- foreground invocation → `POST /api/v1/tool-invocations`
- background invocation → `arguments.background: true`
- polling / wait → `GET /api/v1/tool-invocations/{id}/wait`
- SSE event stream → `GET /api/v1/tool-invocations/{id}/events`

자세한 내용은 [Relay 중계 예제](relay-example.md)에서 확인할 수 있고, 구현 전 설계 판단은 [중계 예제 구현 계획(보관)](relay-toolcalling-plan.md)에서 볼 수 있습니다.
