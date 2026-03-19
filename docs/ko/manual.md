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

## 10. 작업 검증 이력 — '짜장면의 역사' 실호출 (5가지 경로 + web_search + system_prompt)

이 저장소가 실제로 동작함을 검증하기 위해 다음 5가지 경로로 모두 성공 확인했습니다.

### 9-1. Python `--api chat` (gpt-4o)

```bash
cd clients/python
LITELLM_MODEL=gpt-4o uv run python -m litellm_example \
  --api chat --timeout 60 "짜장면의 역사를 3문단으로 설명해줘"
```

> 인천 차이나타운 기원(19세기 말) → 달짝지근한 춘장으로 한국화 → 1960~70년대 배달문화와 결합해 국민 외식 메뉴로 대중화 → 이사·졸업식·블랙데이 상징 음식으로 정착

### 9-2. Python `--api responses` (gpt-4o)

```bash
LITELLM_MODEL=gpt-4o uv run python -m litellm_example \
  --api responses --timeout 60 "짜장면의 역사를 간략히 설명해줘"
```

> 1900년대 초 인천 화교들이 중국 작장면을 한국인 입맛에 맞게 변형(카라멜·춘장) → 1950~60년대 저렴한 한 끼 외식으로 전국 확산

### 9-3. Java `--api chat` (gpt-4o)

```bash
cd clients/java
LITELLM_MODEL=gpt-4o mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api chat --timeout 60 짜장면의 역사를 3문단으로 설명해줘"
```

> 산둥 이주 노동자들이 인천 차이나타운 중심으로 한국화 시작 → 간장 대신 춘장+설탕의 달콤한 소스로 변형, 채소·고기 풍성하게 추가 → 1960~70년대 배달문화와 결합

### 9-4. Java `--api responses` (gpt-4o)

```bash
LITELLM_MODEL=gpt-4o mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api responses --timeout 60 짜장면의 역사를 간략히 설명해줘"
```

> 산둥 출신 화교들이 19세기 말~20세기 초 작장면 전래 → 춘장+기름볶음+감자·당근·양파로 풍부한 맛 완성 → 1960~70년대 배달 외식 대표 메뉴, 독자적 한국 음식으로 정착

### 9-5. Java `--target relay` (gpt-4o, relay 서버 경유)

```bash
# 터미널 A: relay 서버 시작
cd relay && uv run python -m litellm_relay

# 터미널 B: Java relay 호출
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 60 짜장면의 역사를 간략히 설명해줘"
```

> 1883년 인천항 개항 시 산둥 화교 이주 → 1905년 공화춘(共和春) 개점으로 첫 공식 판매 → 1950~60년대 춘장 개선·외식 산업 발전으로 대중화 → 블랙데이(4월 14일) 문화와 결합, 역사와 문화를 담은 대표 퓨전 요리로 자리매김

### 9-6. Python `--api responses --web-search` (gpt-4o + 웹 검색)

```bash
LITELLM_MODEL=gpt-4o uv run python -m litellm_example \
  --api responses --web-search --timeout 60 \
  "짜장면의 역사를 웹 검색으로 3문단 정리해줘"
```

> 웹 검색 결과를 실시간으로 반영해 나무위키·네이버 블로그 등 출처와 함께 답변 반환. 공화춘(1905년) 개점, 사자표 춘장(1948년), 1960~70년대 분식 장려 운동 시기별 사실이 출처 URL과 함께 정확히 인용됨.

### 9-7. Java `--api responses --web-search` (gpt-4o + 웹 검색)

```bash
LITELLM_MODEL=gpt-4o mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--api responses --web-search --timeout 60 짜장면의 역사를 웹 검색으로 간략히"
```

> 웹 검색 기반으로 나무위키·위키백과 출처 인용하며 짜장면의 기원·한국화·대중화 3단계를 정확히 서술.

---

## 11. 요약

- direct Python/Java 예제는 OpenAI 호환 `chat/completions`, `responses`, `background: true`를 지원합니다.
- `--web-search` 플래그로 `web_search_preview` tool을 켜면 일반 모델(gpt-4o 등)에도 실시간 웹 검색을 추가할 수 있습니다.
- `--timeout <초>`로 응답 대기 시간을 조정할 수 있습니다 (기본값 30초, o3-deep-research는 300초 이상 권장).
- relay `deep_research` wrapper는 `arguments.system_prompt` 필드를 통해 모델 수준 지시문(페르소나, 출력 언어, 형식)을 Responses API `instructions` 필드로 전달합니다.
- relay 예제는 LiteLLM Python SDK + FastAPI + Hypercorn으로 구현되어 있습니다.
- Java는 `--target relay` 모드로 relay를 호출할 수 있습니다.
- relay 외부 계약은 `tool_name` + 구조화된 `arguments` 중심이며, raw upstream `input`은 내부에만 존재합니다.
- 문서 사이트는 GitHub Pages에서 한국어로 출판됩니다.
