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

클라이언트가 Chat Completions에 `deep_research` function schema를 붙여서 1차 호출 → tool call 감지 → relay 호출 → 2차 완성 호출을 직접 수행합니다.

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
relay가 실제 deep_research 실행 후 결과 반환
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

### 4-4. Java relay 클라이언트에서 사용

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 120 짜장면의 역사를 알려줘"
```

또는 Java 코드에서 직접:

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

### 4-5. Relay 설정 — chat model

relay의 chat orchestration에 사용하는 모델은 `LITELLM_CHAT_MODEL` 환경변수로 지정합니다 (기본값 `gpt-4o`). deep_research 수행에는 기존 `LITELLM_MODEL`을 사용합니다.

```bash
LITELLM_CHAT_MODEL=gpt-4o-mini \  # orchestration용 (function calling 지원 필요)
LITELLM_MODEL=o3-deep-research \  # 실제 deep research용
uv run python -m litellm_relay
```

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

### 7-1. Approach C: relay `/api/v1/chat` — 단순 인사 (tool 미호출)

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "안녕하세요!", "auto_tool_call": true}'
```

```json
{
  "content": "안녕하세요! 무엇을 도와드릴까요?",
  "tool_called": false,
  "tool_name": null,
  "research_summary": null
}
```

→ 모델이 단순 인사에는 deep_research를 호출하지 않음. ✅

### 7-2. Approach C: relay `/api/v1/chat` — 역사 질문 (tool 자동 호출)

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "짜장면의 역사를 자세히 알려줘", "auto_tool_call": true}'
```

```json
{
  "content": "짜장면의 역사는 19세기 말 중국 산둥 지방 출신 화교들이 인천 차이나타운에서...",
  "tool_called": true,
  "tool_name": "deep_research",
  "research_summary": "# 짜장면의 역사\n..."
}
```

→ 모델이 스스로 deep_research를 호출하고, relay가 연구를 수행한 뒤 최종 답변 합성. ✅

### 7-3. Approach A: Python `--auto-tool-call`

```bash
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example --auto-tool-call --timeout 120 \
  "짜장면의 역사를 자세히 알려줘"
```

→ stdout: 최종 자연어 답변, stderr: `[deep_research was called automatically]` ✅

### 7-4. Approach A: Java `--auto-tool-call`

```bash
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--auto-tool-call --timeout 120 짜장면의 역사를 자세히 알려줘"
```

→ stdout: 최종 자연어 답변, stderr: `[deep_research was called automatically]` ✅

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
