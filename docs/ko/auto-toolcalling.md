# 자동 Tool Calling — 일반 대화 중 deep_research 자동 개입

이 페이지는 일반 대화(chat) 중에 모델이 스스로 `deep_research` 도구를 선택해서 호출하는
**자동 tool calling** 기능을 설명합니다.

---

## 1. 개념: Function Calling이란?

기존 방식에서는 항상 사용자가 명시적으로 `POST /api/v1/tool-invocations`를 호출해야
deep research가 실행됐습니다.

자동 tool calling은 다릅니다. OpenAI의 **function calling** 패턴을 활용하면 모델이
스스로 "이 질문은 deep_research가 필요하다"고 판단해서 도구를 자동으로 호출합니다.

```
사용자: "짜장면의 역사를 자세히 알려줘"
         ↓
  모델 판단: "이건 deep_research가 필요한 질문이다"
         ↓
  모델 → deep_research("짜장면의 역사") 호출
         ↓
  deep_research 실행 (실제 연구 수행)
         ↓
  모델이 연구 결과를 읽고 자연어로 답변 합성
         ↓
사용자: 최종 답변 수령
```

---

## 2. 세 가지 접근 방법

이 저장소는 세 가지 방법을 모두 구현하고 평가합니다.

| 방법 | 누가 tool call을 실행? | 클라이언트 부담 | 투명성 |
|------|----------------------|----------------|--------|
| **A: Client-side** (Python/Java) | 클라이언트 직접 | 높음 (3-turn 로직 직접 구현) | 낮음 (구현 필요) |
| **C: Relay-side** (`/api/v1/chat`) | relay 서버 | 낮음 (단순 POST) | 높음 (완전 투명) |
| **B: Responses API** | 모델/LiteLLM | 낮음 | 모델 종속 |

---

## 3. Approach A — Client-Side Function Calling

클라이언트가 Chat Completions에 `deep_research` function schema를 붙여서 1차 호출 → tool call 감지 → relay-side chat orchestration 위임 → 2차 완성 호출을 직접 수행합니다.

### 3-1. Python — `--auto-tool-call` 플래그

```bash
cd clients/python

# relay 서버가 떠 있어야 합니다 (터미널 A)
# cd relay && uv run python -m litellm_relay

# Python 클라이언트에서 자동 tool calling (터미널 B)
LITELLM_MODEL=gpt-4o \
RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example \
  --auto-tool-call \
  --timeout 120 \
  "짜장면의 역사를 자세히 알려줘"
```

도구가 호출됐으면 stderr에 `[deep_research was called automatically]`가 출력됩니다.

코드에서 직접 사용:

```python
from litellm_example.client import LiteLLMClient

client = LiteLLMClient(base_url, api_key, model="gpt-4o")
answer, tool_called = client.create_chat_with_tool_calling(
    "짜장면의 역사를 자세히 알려줘",
    relay_base_url="http://127.0.0.1:8080",
)
print(answer)
if tool_called:
    print("[deep_research가 자동으로 호출됐습니다]")
```

### 3-2. Java — `--auto-tool-call` 플래그

```bash
cd clients/java

# relay 서버 실행 후
LITELLM_MODEL=gpt-4o \
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--auto-tool-call --timeout 120 짜장면의 역사를 자세히 알려줘"
```

코드에서 직접 사용:

```java
LiteLlmClient client = new LiteLlmClient(baseUrl, apiKey, "gpt-4o");
String[] result = client.createChatWithToolCalling(
    "짜장면의 역사를 자세히 알려줘",
    "http://127.0.0.1:8080"
);
System.out.println(result[0]);
if ("true".equals(result[1])) {
    System.err.println("[deep_research가 자동으로 호출됐습니다]");
}
```

### 3-3. Approach A 내부 동작

```
클라이언트 → POST /v1/chat/completions
              {model, messages, tools: [deep_research schema]}
                    ↓
모델 응답: finish_reason="tool_calls"
           tool_calls: [{function: {name: "deep_research", arguments: {...}}}]
                    ↓
클라이언트 → POST /api/v1/chat (relay)
              {message: "짜장면의 역사", auto_tool_call: true}
                    ↓
relay가 chat orchestration을 다시 수행하고,
필요하다고 판단하면 내부에서 deep_research 실행
                    ↓
클라이언트 → POST /v1/chat/completions (2nd turn)
              {messages: [..., tool result]}
                    ↓
모델이 tool 결과를 읽고 최종 자연어 답변 합성
```

---

## 4. Approach C — Relay-Side Orchestration (`POST /api/v1/chat`)

클라이언트는 단순히 chat 메시지 하나만 보내면 됩니다. relay가 내부적으로 모든 orchestration을 처리합니다.

### 4-1. API 사용법

```bash
# relay 서버 실행
cd relay && LITELLM_CHAT_MODEL=gpt-4o uv run python -m litellm_relay

# 일반 대화 (tool 필요 없음)
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "안녕하세요!",
    "auto_tool_call": true
  }'
```

**예상 응답 (tool 미호출):**
```json
{
  "content": "안녕하세요! 무엇을 도와드릴까요?",
  "tool_called": false,
  "tool_name": null,
  "research_summary": null
}
```

```bash
# deep_research가 필요한 질문
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사를 자세히 알려줘",
    "auto_tool_call": true
  }'
```

**예상 응답 (tool 호출됨):**
```json
{
  "content": "짜장면은 19세기 말 중국 산둥 지방 출신 이민자들이 인천 차이나타운에서...",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "# 짜장면의 역사\n\n..."
}
```

### 4-2. `auto_tool_call: false`로 tool 비활성화

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사를 자세히 알려줘",
    "auto_tool_call": false
  }'
```

모델의 사전 학습 지식으로만 답변하고, deep_research를 호출하지 않습니다.

### 4-3. context 추가

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "이 재료들을 이용한 음식의 역사를 알려줘",
    "context": ["춘장", "중화면", "돼지고기"],
    "auto_tool_call": true
  }'
```

`context` 배열은 user 메시지 앞에 붙어서 모델에게 추가 맥락을 제공합니다.

### 4-4. system_prompt — deep_research에 페르소나·언어·형식 주입

`system_prompt` 필드는 deep_research 실행 시 Responses API `instructions` 필드로 전달됩니다. 모델이 연구 결과를 생성할 때 페르소나·출력 언어·형식을 강제할 때 사용합니다.

```bash
# 항상 영어로 답변하도록 강제
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사를 자세히 알려줘",
    "auto_tool_call": true,
    "system_prompt": "Always answer in English only."
  }'
```

**응답 예시:**
```json
{
  "content": "The history of Jajangmyeon originates from the late 19th to early 20th centuries...",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "The history of Jajangmyeon originates from..."
}
```

```bash
# 초등학생 페르소나로 답변 요청
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사를 알려줘",
    "auto_tool_call": true,
    "system_prompt": "당신은 초등학생에게 설명하는 선생님입니다. 쉬운 말로 2문장으로만 답하세요."
  }'
```

**응답 예시:**
```json
{
  "content": "옛날 중국에서 먹던 작장면이 한국에 들어와 바뀌며 짜장면이 되었어요. 1900년대 초반 인천 차이나타운에서 처음 만들어졌답니다!",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "..."
}
```

> **주의**: `system_prompt`는 deep_research tool이 실제로 호출될 때만 적용됩니다. 모델이 tool 없이 직접 답변하는 경우에는 영향을 주지 않습니다.

| `system_prompt` 활용 패턴 | 예시 |
|--------------------------|------|
| 출력 언어 강제 | `"Always answer in English only."` |
| 페르소나 주입 | `"당신은 초등학생 선생님입니다. 쉬운 말로 설명하세요."` |
| 출력 길이 제한 | `"Answer in exactly two sentences."` |
| 형식 강제 | `"Respond only with a numbered list. No prose."` |
| 도메인 전문성 | `"You are a Korean food historian. Emphasize cultural context."` |

### 4-5. deliverable_format — 산출물 형식 폴백 지정

`deliverable_format` 필드는 deep_research 실행 시 산출물 형식의 **폴백** 값입니다. 모델이 tool call 인자에서 형식을 직접 지정하면 그 값이 우선됩니다.

```bash
# 상세 보고서 형식으로 요청
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사와 사회적 영향을 상세히 알려줘",
    "auto_tool_call": true,
    "deliverable_format": "markdown_report"
  }'
```

| `deliverable_format` 값 | 설명 |
|------------------------|------|
| `"markdown_brief"` (기본값) | 간략한 마크다운 보고서 |
| `"markdown_report"` | 상세 마크다운 보고서 |
| `"json_outline"` | JSON 구조의 개요 |

모델이 tool call 인자에서 `deliverable_format`을 지정하면 모델 지정값이 우선됩니다. 지정하지 않으면 이 필드의 값이 폴백으로 사용됩니다.

### 4-6. Java relay 클라이언트에서 사용

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 120 짜장면의 역사를 알려줘"
```

또는 Java 코드에서 직접 (기본 2-인자 버전):

```java
import example.litellm.relay.RelayClient;
import java.time.Duration;

RelayClient client = new RelayClient("http://127.0.0.1:8080", Duration.ofSeconds(120));
RelayClient.ChatResult result = client.invokeChat("짜장면의 역사를 자세히 알려줘", true);
System.out.println(result.content());
if (result.toolCalled()) {
    System.out.println("[연구 도구 호출됨: " + result.toolName() + "]");
}
```

`system_prompt`와 `deliverable_format`을 지정하는 4-인자 버전:

```java
RelayClient client = new RelayClient("http://127.0.0.1:8080", Duration.ofSeconds(120));
RelayClient.ChatResult result = client.invokeChat(
    "짜장면의 역사를 자세히 알려줘",
    true,                                  // auto_tool_call
    "Always answer in English only.",      // system_prompt
    "markdown_report"                      // deliverable_format (폴백)
);
System.out.println(result.content());
```

### 4-7. Relay 설정 — chat model과 timeout

relay의 chat orchestration에 사용하는 모델은 `LITELLM_CHAT_MODEL` 환경변수로 지정합니다 (기본값 `gpt-4o`). deep_research 수행에는 기존 `LITELLM_MODEL`을 사용합니다.

```bash
LITELLM_CHAT_MODEL=gpt-4o-mini
LITELLM_MODEL=o3-deep-research
uv run python -m litellm_relay
```

### 4-8. Timeout 설정 — chat timeout vs research timeout

`/api/v1/chat` 엔드포인트는 두 가지 단계를 거치므로 timeout이 분리됩니다.

| 환경변수 | 기본값 | 적용 대상 |
|---------|-------|---------|
| `RELAY_TIMEOUT_SECONDS` | `30` | Chat Completions turns (1차, 2차) |
| `RELAY_RESEARCH_TIMEOUT_SECONDS` | `300` | deep_research 실행 (o3-deep-research 호출) |

```bash
# o3-deep-research는 최대 10분 이상 소요될 수 있음
RELAY_RESEARCH_TIMEOUT_SECONDS=600 \
LITELLM_CHAT_MODEL=gpt-4o \
LITELLM_MODEL=o3-deep-research \
uv run python -m litellm_relay
```

> **중요**: `RELAY_TIMEOUT_SECONDS`만 늘리면 Chat Completions는 빨라지지만 deep_research timeout은 여전히 기본 300초입니다. o3-deep-research를 사용할 때는 `RELAY_RESEARCH_TIMEOUT_SECONDS`를 조정하세요.

### 4-9. 에러 처리

deep_research 실행 중 오류가 발생하더라도 relay는 HTTP 500 대신 구조화된 `ChatResponse`를 반환합니다.

```json
{
  "content": "deep_research failed: litellm.Timeout: Connection timed out after 30.0 seconds.",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "deep_research failed: ..."
}
```

이를 통해 클라이언트가 오류 여부를 `tool_called` + `content` 내용으로 판단할 수 있습니다.

---

## 5. Approach B — Responses API Function Calling (평가 결과)

`POST /v1/responses`에 `tools=[{type:"function", ...}]`를 붙여 Responses API 레벨에서 function calling을 시도할 수 있습니다.

### 5-1. 평가 방법

```bash
cd clients/python
LITELLM_MODEL=gpt-4o \
LITELLM_BASE_URL=https://your-host/v1 \
LITELLM_API_KEY=sk-... \
uv run python scripts/eval_responses_function_calling.py
```

### 5-2. 평가 결과

> **테스트 환경**: LiteLLM Proxy + Azure OpenAI (gpt-4o)

| 테스트 | 결과 |
|--------|------|
| `POST /v1/responses` + `tools` (gpt-4o) | ⚠️ LiteLLM Proxy 버전에 따라 다름 |
| Responses API의 function calling 공식 지원 | gpt-4o: 지원, o3-deep-research: 미지원 |
| Chat Completions function calling 대비 안정성 | Chat Completions가 더 안정적 |

> **권장**: 자동 tool calling에는 **Approach A** (Chat Completions + function calling) 또는 **Approach C** (relay-side)를 사용하세요. Responses API function calling은 LiteLLM Proxy 버전 및 upstream 모델 설정에 따라 동작이 달라질 수 있습니다.

---

## 6. 모델 지원 현황

| 모델 | Chat Completions function calling | Responses API function calling |
|------|----------------------------------|-------------------------------|
| `gpt-4o` | ✅ 완전 지원 | ⚠️ 프록시 설정 종속 |
| `gpt-4o-mini` | ✅ 완전 지원 | ⚠️ 프록시 설정 종속 |
| `o3-deep-research` | ❌ 미지원 (연구 모델) | ❌ 미지원 |

> **중요**: `o3-deep-research`는 자체 내부 도구로 심층 조사를 수행하는 모델이므로 표준 function calling을 지원하지 않습니다. 자동 tool calling 시나리오에서 o3-deep-research는 **피호출자** (deep_research tool의 실제 실행 모델)이고, **호출자** (function calling을 결정하는 모델)는 gpt-4o 등 function calling 지원 모델이어야 합니다.

---

## 7. 실제 호출 검증 결과

> **검증 환경**: LiteLLM Proxy (gpt-4o + o3-deep-research), relay 서버 로컬 기동
> **relay 기동 명령**: `LITELLM_CHAT_MODEL=gpt-4o RELAY_RESEARCH_TIMEOUT_SECONDS=300 uv run python -m litellm_relay`

### 7-1. Approach C: relay `/api/v1/chat` — 단순 인사 (tool 미호출)

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요, 오늘 날씨 어때요?", "auto_tool_call": true}'
```

**실제 응답:**
```json
{
  "content": "안녕하세요! 현재는 날씨 정보를 제공할 수 있는 기능이 활성화되어 있지 않습니다...",
  "tool_called": false,
  "tool_name": null,
  "research_summary": null
}
```

→ 모델이 단순 인사에는 deep_research를 호출하지 않음. ✅

### 7-2. Approach C: relay `/api/v1/chat` — 역사 조사 (tool 자동 호출)

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "짜장면의 역사와 기원에 대해 상세하게 조사해서 알려줘", "auto_tool_call": true}'
```

**실제 응답:**
```json
{
  "content": "짜장면은 중국에서 유래된 자장몐(炸酱面)을 바탕으로 한국에서 발전한 음식으로, 20세기 초반 중국 산둥 출신 이민자들에 의해 한국에 소개되었습니다...",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "# 짜장면의 역사와 기원에 관한 상세 연구\n\n짜장면은 한국에서 매우 사랑받는 요리로..."
}
```

→ 모델이 스스로 deep_research를 호출하고, relay가 o3-deep-research로 연구 수행 후 최종 답변 합성. ✅

### 7-3. Approach A: Python `--auto-tool-call`

```bash
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example --auto-tool-call --timeout 300 \
  "BTS의 역사와 성공 요인에 대해 조사해줘"
```

**실제 결과:**
- stderr: `[deep_research was called automatically]`
- stdout: BTS 역사, 성공 요인, 주요 업적을 포함한 구조화된 마크다운 보고서 반환

→ 단일 CLI 명령으로 function calling → deep research → 답변 합성까지 완전 자동화. ✅

### 7-4. Approach A: Java `--auto-tool-call`

```bash
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--auto-tool-call --timeout 300 짜장면의 역사를 자세히 알려줘"
```

→ stdout: 최종 자연어 답변, stderr: `[deep_research was called automatically]` ✅

### 7-5. 타임아웃 분리 검증

기존 버그: `RELAY_TIMEOUT_SECONDS=30` (기본값)을 research에도 적용해 30초 후 500 오류 발생.

수정 후: `RELAY_RESEARCH_TIMEOUT_SECONDS=300` (기본값)이 deep_research에 독립적으로 적용됨.

```
ChatOrchestrator.timeout_seconds          → Chat Completions turns (30s 기본)
ChatOrchestrator.research_timeout_seconds → deep_research 실행 (300s 기본)
```

→ 30초 타임아웃으로 인한 500 오류 해결. ✅

---

## 8. 언제 어떤 방법을 써야 할까?

| 상황 | 권장 방법 |
|------|---------|
| 간단한 단발성 호출 | Approach C (`/api/v1/chat`) |
| 클라이언트에서 tool call 여부를 직접 제어하고 싶을 때 | Approach A |
| Java relay 클라이언트 | Approach C (`invokeChat`) |
| tool 호출 여부를 감추고 싶을 때 | Approach C |
| deep_research가 필요한지 불확실한 대화 | Approach C (auto_tool_call=true) |
| 항상 deep_research를 쓰고 싶을 때 | 기존 `POST /api/v1/tool-invocations` |
| 연구 결과의 언어·페르소나를 제어하고 싶을 때 | Approach C + `system_prompt` |
| 상세 보고서 형식을 원할 때 | Approach C + `deliverable_format="markdown_report"` |
