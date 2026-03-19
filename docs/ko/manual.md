# LiteLLM o3-deep-research 한국어 매뉴얼

이 저장소는 `o3-deep-research` 모델을 LiteLLM 호환 방식으로 호출하는 **세 가지 예제**를 제공합니다.

1. `clients/python/` — Python 직접 호출 예제
2. `clients/java/` — Java 직접 호출 + relay 호출 예제
3. `relay/` — LiteLLM Python SDK + FastAPI + Hypercorn 중계 예제

직접 호출 예제는 OpenAI 호환 API 스타일인 다음 두 경로를 사용합니다.

- `POST /v1/chat/completions`
- `POST /v1/responses`

relay 예제는 raw `input` 문자열 대신 구조화된 **tool invocation 계약**을 사용합니다.

## 1. 저장소 개요

- Python 예제는 LiteLLM Proxy를 직접 호출합니다.
- Java 예제는 LiteLLM Proxy를 직접 호출할 수도 있고, relay를 호출할 수도 있습니다.
- relay 예제는 LiteLLM Python SDK를 내부에서 사용하고, FastAPI + Hypercorn으로 외부 API를 제공합니다.
- 테스트는 기본적으로 mock/local harness 중심이라서 실제 서버 없이도 돌아갑니다.
- 실제 LiteLLM Proxy가 있으면 direct/relay 둘 다 실호출 검증이 가능합니다.

## 2. 공통 사전 준비

다음 값이 필요합니다.

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택 사항, 기본값 `o3-deep-research`)

권장 방법은 홈 디렉터리의 `~/.env` 파일에 넣는 것입니다.

```dotenv
LITELLM_API_KEY=sk-your-lite-llm-api-key
LITELLM_BASE_URL=https://localhost:4000/v1
LITELLM_MODEL=o3-deep-research
```

### `uv` 설치 (Python 예제 / relay 예제용)

이 저장소의 Python 예제와 relay 예제는 `uv`를 기본 패키지/실행 도구로 사용합니다.

macOS / Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

설치 후 새 셸을 열거나, 안내된 PATH 설정을 반영한 뒤 확인합니다.

```bash
uv --version
```

`uv`가 아직 PATH에 없으면 다음처럼 직접 경로를 추가할 수 있습니다.

```bash
export PATH="$HOME/.local/bin:$PATH"
uv --version
```

Windows는 공식 설치 안내를 참고하세요.

- <https://docs.astral.sh/uv/getting-started/installation/>

> **참고:** Java 예제만 사용할 경우 `uv`는 필수가 아니지만, relay 서버를 실행하거나 Python 예제를 검증하려면 필요합니다.

### `LITELLM_BASE_URL` 규칙

다음 형태를 지원합니다.

- `https://localhost:4000`
- `https://localhost:4000/v1`

direct Python/Java 예제는 내부적으로 `/v1/` API 루트로 정규화해서 사용합니다. relay 예제는 `LITELLM_BASE_URL`을 LiteLLM SDK의 `api_base`로 그대로 넘기므로, upstream LiteLLM Proxy 기준으로 root URL 또는 `/v1` URL을 사용할 수 있습니다.

보안상 Python direct 예제는 원격 호스트에 대해 평문 `http://`를 허용하지 않습니다. 즉, 로컬 개발(`localhost`, `127.0.0.1`)이 아닌 경우에는 `https://`를 써야 합니다.

## 3. Python 직접 호출 예제

경로:

```bash
cd clients/python
```

### 의존성 설치 및 테스트

```bash
uv sync --all-extras --dev
uv run pytest
```

### chat/completions 호출

```bash
uv run python -m litellm_example "Reply with exactly: OK"
```

### responses 호출

```bash
uv run python -m litellm_example --api responses "Reply with exactly: OK"
```

### responses background 제출

```bash
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
```

이 경우 최종 텍스트 대신 `id`, `status` 같은 후속 추적용 메타데이터가 담긴 원본 JSON을 출력합니다.

### 타임아웃 조정 (--timeout)

기본 타임아웃은 30초입니다. `o3-deep-research`처럼 응답 시간이 긴 모델을 사용할 때는 `--timeout <초>`를 늘리세요.

```bash
uv run python -m litellm_example --timeout 300 "짜장면의 역사를 조사해줘"
uv run python -m litellm_example --api responses --timeout 300 "짜장면의 역사를 조사해줘"
```

## 4. Java 예제

경로:

```bash
cd clients/java
```

### 빌드 및 테스트

```bash
mvn test
```

### 4-1. direct chat/completions 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
```

### 4-2. direct responses 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
```

### 4-3. direct responses background 제출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

### 4-4. relay 호출 모드

relay 서버가 이미 떠 있다고 가정하면 다음처럼 Java에서 relay를 호출할 수 있습니다.

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay Summarize relay architecture"
```

background 제출:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay --background Summarize relay architecture"
```

stream:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay --stream Summarize relay architecture"
```

### 4-5. 타임아웃 조정 (--timeout)

기본 타임아웃은 30초입니다. direct 및 relay 호출 모두 `--timeout <초>`로 조정할 수 있습니다.

```bash
# direct 호출 타임아웃 늘리기
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--timeout 300 짜장면의 역사를 조사해줘"

# relay 호출 타임아웃 늘리기
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 300 짜장면의 역사를 조사해줘"
```

## 5. relay 중계 예제

경로:

```bash
cd relay
```

### relay 전용 설정

relay는 공통 upstream 설정 외에도 다음 값을 쓸 수 있습니다.

- `RELAY_HOST` (기본 `127.0.0.1`)
- `RELAY_PORT` (기본 `8080`)
- `RELAY_TIMEOUT_SECONDS` (기본 `30`)

### 실행

```bash
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_relay
```

### 공개 API

- `POST /api/v1/tool-invocations`
- `GET /api/v1/tool-invocations/{invocation_id}`
- `GET /api/v1/tool-invocations/{invocation_id}/wait`
- `GET /api/v1/tool-invocations/{invocation_id}/events`

### 공개 계약 예시

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "Azure OpenAI o3-deep-research relay 구조를 설명해줘",
    "context": ["Azure Landing Zone", "LiteLLM Proxy"],
    "constraints": ["markdown 형식", "보안 경계 설명"],
    "deliverable_format": "markdown_brief",
    "require_citations": true,
    "background": false,
    "stream": false
  }
}
```

relay 내부에서만 위 구조를 LiteLLM Responses 요청으로 변환하며, 내부 모델 이름은 `litellm_proxy/<model>` 형태를 사용합니다.

## 6. `background` 와 `stream` 해석

### 6-1. direct 예제의 `background`

- direct Python/Java CLI는 foreground 1회성 프로세스입니다.
- `--background`는 로컬 프로세스를 daemon으로 바꾸는 것이 아니라, 서버 측 Responses 작업을 background 모드로 제출하는 것입니다.

### 6-2. relay 예제의 `stream`

- relay는 `POST /api/v1/tool-invocations`로 invocation을 만들고,
- `GET /api/v1/tool-invocations/{invocation_id}/events`로 `text/event-stream`을 제공합니다.
- 현재 구현은 text delta만 중계하는 **text-focused SSE 예제**입니다.

## 7. 문제 해결

### `LITELLM_API_KEY is not set`

- 환경변수가 없거나
- `~/.env` 파일이 없거나
- 값이 비어 있을 수 있습니다.

확인:

```bash
echo "$LITELLM_API_KEY"
cat ~/.env
```

### `LITELLM_BASE_URL is not set`

예시:

```dotenv
LITELLM_BASE_URL=https://your-litellm-host/v1
```

### `RELAY_BASE_URL` 오류

Java relay 모드는 `RELAY_BASE_URL`이 없으면 기본값 `http://127.0.0.1:8080`을 사용합니다. 다른 주소를 쓰고 있다면 환경변수를 맞춰야 합니다.

### SSL / 인증서 오류

Python direct 예제는 `certifi` CA 번들을 사용합니다. 그래도 실패하면:

- LiteLLM Proxy 인증서 체인이 정상인지 확인
- 사설 인증서라면 신뢰 저장소 구성이 필요한지 확인

### 4xx / 5xx 응답

점검 항목:

- API 키가 맞는지
- 모델 이름(`o3-deep-research`)이 실제 LiteLLM 설정에서 허용되는지
- 프록시가 `/v1/chat/completions` 또는 `/v1/responses`를 노출하는지
- relay라면 upstream Proxy와 relay의 listen 주소가 모두 맞는지

## 8. web_search_preview — 일반 모델에 웹 검색 켜기

`web_search_preview`는 OpenAI Responses API의 **내장 tool**로, `gpt-4o` 같은 일반 모델에도 실시간 웹 검색 능력을 부여합니다.

### 동작 원리

```
요청: POST /v1/responses
{
  "model": "gpt-4o",
  "input": "짜장면의 역사를 웹 검색으로 정리해줘",
  "tools": [{"type": "web_search_preview"}]
}
```

- 모델이 필요하다고 판단하면 자동으로 웹 검색을 수행하고 결과를 응답에 반영합니다.
- 검색 결과 URL이 출처로 인용되어 답변에 포함될 수 있습니다.
- `o3-deep-research`는 자체적으로 심층 조사를 수행하므로 이 tool이 불필요하지만, `gpt-4o` 같은 범용 모델에서 최신 정보가 필요할 때 유용합니다.

> **주의:** LiteLLM Proxy 설정에서 해당 모델에 대해 `web_search_preview` tool이 허용되어야 합니다.

### Python — `--web-search` 플래그

```bash
# --api responses 와 함께 사용
uv run python -m litellm_example \
  --api responses \
  --web-search \
  --timeout 60 \
  "짜장면의 역사를 웹 검색으로 3문단 정리해줘"
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

> `--web-search`는 반드시 `--api responses`와 함께 사용해야 합니다. `--api chat`에는 적용되지 않습니다.

### Java — `--web-search` 플래그

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api responses --web-search --timeout 60 짜장면의 역사를 웹 검색으로 정리해줘"
```

코드에서 직접 사용:

```java
import example.litellm.LiteLlmClient;
import java.util.List;
import java.util.Map;

LiteLlmClient client = new LiteLlmClient(baseUrl, apiKey, "gpt-4o");
String result = client.createResponse(
        "짜장면의 역사를 웹 검색으로 정리해줘",
        false,
        List.of(Map.of("type", "web_search_preview"))
);
System.out.println(result);
```

### 실제 호출 결과 예시 (gpt-4o + web_search_preview)

```
1. **짜장면의 기원**
짜장면은 중국 산둥 지역의 전통 가정식인 '작장면(炸酱面)'에서 유래된 음식으로,
1883년 인천항 개항 이후 한국에 들어오게 되었습니다. 산둥 출신 화교들은
차이나타운 부근에서 춘장과 면을 이용해 간단히 만들어 먹기 시작했습니다.
[출처: 나무위키]

2. **한국식 짜장면으로의 변화**
1948년, 영화식품의 왕송산이 춘장에 캐러멜을 첨가해 단맛을 강조한 '사자표 춘장'을
출시하며 짜장면은 한국화의 결정적 계기를 마련했습니다. [출처: 네이버 블로그]

3. **현대의 짜장면**
졸업식·입학식 등 특별한 날의 상징이자 배달 음식의 대명사로 자리 잡았으며,
간짜장·삼선짜장 등 다양한 변주로 세분화되어 있습니다. [출처: 티스토리 블로그]
```

---

## 9. deep_research Wrapper의 Prompt 구조와 system_prompt

### 9-1. 현재 구조

relay의 `deep_research` wrapper는 모든 요청을 Responses API의 **단일 `input` 문자열**로 조립해서 보냅니다.

```
Tool: deep_research
Research question: {research_question}
Deliverable format: {deliverable_format}
Require citations: yes/no
Context:
- ...
Constraints:
- ...
```

이 문자열이 모델의 user turn으로 전달됩니다.

### 9-2. 문제: 시스템 프롬프트(지시문)를 어디에 넣어야 하나?

**잘못된 방법** — `research_question` 안에 섞기:

```json
{
  "research_question": "System: 반드시 영어로만 답하라.\n\n짜장면의 역사를 설명해줘"
}
```

이렇게 하면 "System:"이 그냥 user 메시지의 일부로 처리되어 모델에 대한 **강제력이 없습니다**. 모델이 무시하거나 그대로 출력에 포함할 수 있습니다.

**올바른 방법** — `system_prompt` 필드 사용:

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "짜장면의 역사를 설명해줘",
    "deliverable_format": "markdown_brief",
    "system_prompt": "반드시 영어로만 답하라."
  }
}
```

relay는 `system_prompt`를 Responses API의 **`instructions`** 필드로 전달합니다. 이것이 Chat Completions의 `system` role, Responses API의 `developer` role과 동등한 **모델 수준 지시문**입니다.

### 9-3. Responses API의 prompt 레이어 구조

```
┌─────────────────────────────────────────────┐
│  instructions (system/developer layer)      │  ← system_prompt 매핑
│  "반드시 영어로만 답하라."                   │
├─────────────────────────────────────────────┤
│  input (user turn)                          │  ← _render_input() 결과
│  "Tool: deep_research                       │
│   Research question: 짜장면의 역사를 설명해줘│
│   Deliverable format: markdown_brief        │
│   Require citations: yes"                   │
└─────────────────────────────────────────────┘
```

- **`instructions`** (= `system_prompt`): 페르소나, 출력 언어, 형식 강제 등 모델 행동을 제어
- **`input`** (= research_question + 나머지): 실제 조사 요청

### 9-4. 실제 테스트 결과

**아무 system_prompt 없을 때 (한국어 질문 → 한국어 답변):**

```bash
curl -X POST http://127.0.0.1:8080/api/v1/tool-invocations \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "deep_research",
    "arguments": {
      "research_question": "짜장면의 역사를 한 문장으로 설명해줘",
      "deliverable_format": "markdown_brief"
    }
  }'
```

```
짜장면의 역사는 19세기 말 중국 산둥 지방 출신 이민자들이 인천
차이나타운에서 중국 요리인 '작장면'을 한국화하며 시작되었다.
```

**`system_prompt`로 영어 강제:**

```bash
curl -X POST http://127.0.0.1:8080/api/v1/tool-invocations \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "deep_research",
    "arguments": {
      "research_question": "짜장면의 역사를 한 문장으로 설명해줘",
      "deliverable_format": "markdown_brief",
      "system_prompt": "You are a food historian. Always answer in English only."
    }
  }'
```

```
The history of Jajangmyeon originates from the late 19th to early 20th
centuries, evolving from a Shandong-style Chinese noodle dish and
adapting to Korean tastes in Incheon's Chinese immigrant community.
```

**`system_prompt`로 페르소나 주입 (초등학생 선생님):**

```bash
curl -X POST http://127.0.0.1:8080/api/v1/tool-invocations \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "deep_research",
    "arguments": {
      "research_question": "짜장면의 역사를 설명해줘",
      "deliverable_format": "markdown_brief",
      "system_prompt": "당신은 초등학생에게 설명하는 선생님입니다. 최대 2문장으로, 쉬운 말로 설명하세요.",
      "require_citations": false
    }
  }'
```

```
옛날 중국에서 먹던 "작장면"이라는 요리가 한국에 들어와 조금씩 바뀌며
우리가 아는 짜장면이 되었어요. 한국에서는 1900년대 초반 인천
차이나타운에서 처음 만들어지며 지금까지 사랑받는 음식이 되었답니다!
```

### 9-5. system_prompt 활용 패턴 정리

| 목적 | system_prompt 예시 |
|------|--------------------|
| 출력 언어 강제 | `"Always answer in English only."` |
| 페르소나 주입 | `"당신은 초등학생 선생님입니다. 쉬운 말로 설명하세요."` |
| 출력 길이 제한 | `"Answer in exactly one sentence."` |
| 형식 강제 | `"Respond only with a numbered list. No prose."` |
| 도메인 전문성 | `"You are a Korean food historian. Emphasize cultural context."` |
| 인용 스타일 제어 | `"Use APA citation style for all references."` |

### 9-6. Chat Completions API와의 비교

| | Chat Completions | Responses API (relay 사용 시) |
|-|-----------------|-------------------------------|
| system prompt | `messages[{role:"system", content:...}]` | `instructions` 필드 (= `system_prompt`) |
| user prompt | `messages[{role:"user", content:...}]` | `input` 필드 (= `_render_input()` 결과) |
| developer prompt | `messages[{role:"developer", content:...}]` | `instructions` 필드 |
| relay 외부 계약 | 해당 없음 | `arguments.system_prompt` |

### 9-7. `system_prompt`가 없을 때와 있을 때의 흐름

```
system_prompt 없음:
  relay → litellm.responses(input="Tool: deep_research\nResearch question: ...", ...)

system_prompt 있음:
  relay → litellm.responses(
    input="Tool: deep_research\nResearch question: ...",
    instructions="페르소나/언어/형식 지시",
    ...
  )
```

---

## 10. deep_research Wrapper에서 JSON 출력 강제 (text_format)

### 10-1. 배경

relay wrapper의 `_render_input()`은 모든 요청을 Markdown 형식의 문자열로 조립해 Responses API의 `input` 필드로 보냅니다. 모델은 기본적으로 plain text / Markdown으로 답합니다.

`deliverable_format: "json_outline"`을 지정해도 이것은 **텍스트 힌트에 불과**합니다. 모델이 무시하거나, JSON을 코드 블럭(```json```)으로 감싸서 반환할 수 있습니다.

```bash
# 현재 json_outline 동작 예
curl -X POST .../api/v1/tool-invocations -d '{"arguments":{"deliverable_format":"json_outline", ...}}'
# 결과: ```json\n{"title": ...}\n```  ← 마크다운 코드 블럭, JSON.parse 불가
```

**API 레벨에서 JSON을 강제**하려면 `text_format` 필드를 사용해야 합니다.

### 10-2. text_format 필드

`text_format`은 Responses API의 `text.format` 객체에 직접 매핑됩니다.

| text_format 값 | 의미 | gpt-4o | o3-deep-research |
|---------------|------|--------|-----------------|
| 없음 (기본값) | plain text / Markdown | ✅ | ✅ |
| `{"type":"json_object"}` | 유효한 JSON 객체 강제 | ✅ | ❌ **API 400 오류** |
| `{"type":"json_schema","name":"...","schema":{...},"strict":true}` | 스키마 준수 JSON 강제 | ✅ | ❌ **API 400 오류** |

### 10-3. 사용 방법

#### json_object 모드 (자유 형식 JSON)

```bash
curl -X POST http://127.0.0.1:8080/api/v1/tool-invocations \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "deep_research",
    "arguments": {
      "research_question": "짜장면의 기원을 JSON으로: origin_country, year_introduced, main_ingredient 키 포함",
      "deliverable_format": "json_outline",
      "text_format": {"type": "json_object"},
      "require_citations": false
    }
  }'
```

**실제 결과 (gpt-4o):**

```json
{
  "origin_country": "China",
  "year_introduced": "Early 20th century (to Korea)",
  "main_ingredient": "Fermented black soybeans, wheat noodles, pork, vegetables"
}
```

#### json_schema 모드 (스키마 강제 JSON)

```bash
curl -X POST http://127.0.0.1:8080/api/v1/tool-invocations \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "deep_research",
    "arguments": {
      "research_question": "짜장면의 역사를 JSON으로 반환해줘",
      "deliverable_format": "json_outline",
      "text_format": {
        "type": "json_schema",
        "name": "food_history",
        "strict": true,
        "schema": {
          "type": "object",
          "properties": {
            "origin_country":      {"type": "string"},
            "introduced_to_korea": {"type": "integer"},
            "key_milestone":       {"type": "string"},
            "is_fusion":           {"type": "boolean"}
          },
          "required": ["origin_country","introduced_to_korea","key_milestone","is_fusion"],
          "additionalProperties": false
        }
      },
      "require_citations": false
    }
  }'
```

**실제 결과 (gpt-4o):**

```json
{
  "origin_country": "China",
  "introduced_to_korea": 1905,
  "key_milestone": "Adjusted recipe to Korean tastes",
  "is_fusion": true
}
```

모든 필드가 스키마 타입과 정확히 일치합니다.

### 10-4. 모델별 지원 현황과 제약

#### gpt-4o (✅ 완전 지원)

- `json_object`: 항상 valid JSON 반환
- `json_schema`: strict mode로 스키마 100% 준수
- 둘 다 `deliverable_format`과 무관하게 동작 (`json_outline` 아니어도 됨)

#### o3-deep-research (❌ 미지원)

```
❌ json_schema: API 레벨에서 즉시 오류 반환
   "Invalid parameter: 'text.format' of type 'json_schema' is not supported
    with model version o3-deep-research-2025-06-26"

❌ json_object: API 레벨에서 즉시 오류 반환
   - structured `text.format` 자체가 기본 o3-deep-research 경로에서 지원되지 않음
   - JSON이 꼭 필요하면 gpt-4o 같은 호환 모델을 사용해야 함
```

**권장 패턴 (JSON 출력이 꼭 필요할 때):**

```json
{
  "arguments": {
    "research_question": "짜장면의 역사를 JSON 형식으로 정리해줘. 필드: origin, period, modernization",
    "deliverable_format": "json_outline",
    "system_prompt": "Return ONLY a JSON object. No prose, no markdown, no code fences.",
    "background": true
  }
}
```

→ API 레벨 JSON 강제가 꼭 필요하면 `gpt-4o` 같은 호환 모델을 사용하세요. 기본 `o3-deep-research` 경로는 plain text / markdown 출력만 지원한다고 보는 편이 안전합니다.

### 10-5. 내부 동작

relay는 `text_format`을 다음과 같이 변환합니다.

```python
# contracts.py
text_format = TextFormatJsonObject()   # {"type": "json_object"}
text_format = TextFormatJsonSchema(    # {"type": "json_schema", "name": ..., "schema": {...}}
    name="food_history",
    schema={...},
    strict=True,
)

# upstream.py
extra_kwargs["text"] = {
    "format": args.text_format.model_dump(by_alias=True, exclude_none=True)
}
# → litellm.responses(..., text={"format": {"type": "json_object"}}, ...)
```

### 10-6. deliverable_format vs text_format

| | `deliverable_format` | `text_format` |
|-|---------------------|---------------|
| 위치 | `_render_input()` → input 문자열 | `text.format` → API 파라미터 |
| 강제력 | **텍스트 힌트** (모델이 무시 가능) | **API 레벨 강제** (위반 시 오류) |
| 지원 모델 | 모든 모델 | gpt-4o 계열 (o3-deep-research 미지원) |
| JSON 보장 | ❌ | ✅ (json_object/json_schema) |

**둘을 같이 쓰는 권장 패턴:**

```json
{
  "deliverable_format": "json_outline",
  "text_format": {"type": "json_object"}
}
```

`deliverable_format: "json_outline"`은 모델이 "JSON 구조로 답하려는 의도"를 인지하는 힌트이고, `text_format`은 API 레벨에서 JSON을 실제로 강제합니다.

---

## 11. 작업 검증 이력 — '짜장면의 역사' 실호출 (7가지 경로 + web_search + system_prompt)

이 저장소가 실제로 동작함을 검증하기 위해 다음 7가지 경로로 모두 성공 확인했습니다.

### 11-1. Python `--api chat` (gpt-4o)

```bash
cd clients/python
LITELLM_MODEL=gpt-4o uv run python -m litellm_example \
  --api chat --timeout 60 "짜장면의 역사를 3문단으로 설명해줘"
```

> 인천 차이나타운 기원(19세기 말) → 달짝지근한 춘장으로 한국화 → 1960~70년대 배달문화와 결합해 국민 외식 메뉴로 대중화 → 이사·졸업식·블랙데이 상징 음식으로 정착

### 11-2. Python `--api responses` (gpt-4o)

```bash
LITELLM_MODEL=gpt-4o uv run python -m litellm_example \
  --api responses --timeout 60 "짜장면의 역사를 간략히 설명해줘"
```

> 1900년대 초 인천 화교들이 중국 작장면을 한국인 입맛에 맞게 변형(카라멜·춘장) → 1950~60년대 저렴한 한 끼 외식으로 전국 확산

### 11-3. Java `--api chat` (gpt-4o)

```bash
cd clients/java
LITELLM_MODEL=gpt-4o mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api chat --timeout 60 짜장면의 역사를 3문단으로 설명해줘"
```

> 산둥 이주 노동자들이 인천 차이나타운 중심으로 한국화 시작 → 간장 대신 춘장+설탕의 달콤한 소스로 변형, 채소·고기 풍성하게 추가 → 1960~70년대 배달문화와 결합

### 11-4. Java `--api responses` (gpt-4o)

```bash
LITELLM_MODEL=gpt-4o mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api responses --timeout 60 짜장면의 역사를 간략히 설명해줘"
```

> 산둥 출신 화교들이 19세기 말~20세기 초 작장면 전래 → 춘장+기름볶음+감자·당근·양파로 풍부한 맛 완성 → 1960~70년대 배달 외식 대표 메뉴, 독자적 한국 음식으로 정착

### 11-5. Java `--target relay` (gpt-4o, relay 서버 경유)

```bash
# 터미널 A: relay 서버 시작
cd relay && uv run python -m litellm_relay

# 터미널 B: Java relay 호출
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 60 짜장면의 역사를 간략히 설명해줘"
```

> 1883년 인천항 개항 시 산둥 화교 이주 → 1905년 공화춘(共和春) 개점으로 첫 공식 판매 → 1950~60년대 춘장 개선·외식 산업 발전으로 대중화 → 블랙데이(4월 14일) 문화와 결합, 역사와 문화를 담은 대표 퓨전 요리로 자리매김

### 11-6. Python `--api responses --web-search` (gpt-4o + 웹 검색)

```bash
LITELLM_MODEL=gpt-4o uv run python -m litellm_example \
  --api responses --web-search --timeout 60 \
  "짜장면의 역사를 웹 검색으로 3문단 정리해줘"
```

> 웹 검색 결과를 실시간으로 반영해 나무위키·네이버 블로그 등 출처와 함께 답변 반환. 공화춘(1905년) 개점, 사자표 춘장(1948년), 1960~70년대 분식 장려 운동 시기별 사실이 출처 URL과 함께 정확히 인용됨.

### 11-7. Java `--api responses --web-search` (gpt-4o + 웹 검색)

```bash
LITELLM_MODEL=gpt-4o mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api responses --web-search --timeout 60 짜장면의 역사를 웹 검색으로 간략히"
```

> 웹 검색 기반으로 나무위키·위키백과 출처 인용하며 짜장면의 기원·한국화·대중화 3단계를 정확히 서술.

---

## 12. 요약

- direct Python/Java 예제는 OpenAI 호환 `chat/completions`, `responses`, `background: true`를 지원합니다.
- `--web-search` 플래그로 `web_search_preview` tool을 켜면 일반 모델(gpt-4o 등)에도 실시간 웹 검색을 추가할 수 있습니다.
- `--timeout <초>`로 응답 대기 시간을 조정할 수 있습니다 (기본값 30초, o3-deep-research는 300초 이상 권장).
- relay `deep_research` wrapper는 `arguments.system_prompt` 필드를 통해 모델 수준 지시문(페르소나, 출력 언어, 형식)을 Responses API `instructions` 필드로 전달합니다.
- `arguments.text_format`으로 API 레벨 JSON 강제가 가능합니다: `json_object`(자유 JSON), `json_schema`(스키마 강제). gpt-4o에서 완전 지원되며, 기본 o3-deep-research 경로에서는 둘 다 지원되지 않습니다.
- relay 예제는 LiteLLM Python SDK + FastAPI + Hypercorn으로 구현되어 있습니다.
- Java는 `--target relay` 모드로 relay를 호출할 수 있습니다.
- relay 외부 계약은 `tool_name` + 구조화된 `arguments` 중심이며, raw upstream `input`은 내부에만 존재합니다.
- 문서 사이트는 GitHub Pages에서 한국어로 출판됩니다.

---

## 13. 자동 Tool Calling — 일반 대화 중 deep_research 자동 개입

자세한 내용은 → [자동 Tool Calling 가이드](auto-toolcalling.md)

### 13-1. 핵심 개념

기존 방식은 항상 사용자가 명시적으로 `deep_research`를 호출해야 했습니다. 자동 tool calling은 모델이 스스로 판단해서 deep_research를 실행합니다.

### 13-2. Approach A: Client-Side (Python/Java)

```bash
# Python
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example --auto-tool-call --timeout 120 \
  "짜장면의 역사를 자세히 알려줘"

# Java
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--auto-tool-call --timeout 120 짜장면의 역사를 자세히 알려줘"
```

클라이언트가 Chat Completions function calling 3-turn 흐름을 직접 처리합니다.

### 13-3. Approach C: Relay-Side (`POST /api/v1/chat`)

```bash
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사를 자세히 알려줘",
    "auto_tool_call": true
  }'
```

relay가 모든 orchestration을 내부에서 처리합니다. 클라이언트는 단순 chat 요청만 보내면 됩니다.

### 13-4. 모델 제약

- **gpt-4o** (orchestration): function calling 완전 지원
- **o3-deep-research** (실제 연구): function calling 미지원 — 항상 피호출자
- orchestration 모델은 `LITELLM_CHAT_MODEL` 환경변수로 지정 (기본 `gpt-4o`)

### 13-5. Timeout 설정 (중요)

`/api/v1/chat`은 두 가지 독립 timeout을 사용합니다.

| 환경변수 | 기본값 | 적용 대상 |
|---------|-------|---------|
| `RELAY_TIMEOUT_SECONDS` | `30` | Chat Completions turns |
| `RELAY_RESEARCH_TIMEOUT_SECONDS` | `300` | deep_research 실행 |

relay 기동 시 `RELAY_RESEARCH_TIMEOUT_SECONDS`를 모델 특성에 맞게 조정하세요.
`o3-deep-research`는 최대 10분 이상 소요될 수 있습니다.

### 13-6. ChatRequest 확장 필드 — system_prompt와 deliverable_format

`POST /api/v1/chat`은 두 가지 추가 필드를 지원합니다.

| 필드 | 타입 | 기본값 | 설명 |
|------|------|--------|------|
| `system_prompt` | `string \| null` | `null` | deep_research 실행 시 Responses API `instructions` 필드로 전달. 페르소나·출력 언어·형식 강제에 사용. |
| `deliverable_format` | `string` | `"markdown_brief"` | deep_research 산출물 형식의 폴백. 모델이 tool call 인자로 형식을 지정하면 모델 지정값이 우선. |

**`system_prompt` 활용 예:**

```bash
# deep_research가 영어로만 답변하도록 강제
curl -X POST http://127.0.0.1:8080/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{
    "message": "짜장면의 역사를 알려줘",
    "auto_tool_call": true,
    "system_prompt": "Always answer in English only."
  }'
```

**`deliverable_format` 활용 예:**

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

**Java 코드 예:**

```java
RelayClient client = new RelayClient("http://127.0.0.1:8080", Duration.ofSeconds(120));

// system_prompt와 deliverable_format 모두 지정 (4-인자 버전)
RelayClient.ChatResult result = client.invokeChat(
    "짜장면의 역사를 자세히 알려줘",
    true,                               // auto_tool_call
    "Always answer in English only.",   // system_prompt
    "markdown_report"                   // deliverable_format (폴백)
);
System.out.println(result.content());
```

자세한 내용은 → [자동 Tool Calling 가이드 — 4-5. deliverable_format](auto-toolcalling.md)
