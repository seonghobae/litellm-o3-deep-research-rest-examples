# LiteLLM SDK + FastAPI + Hypercorn 중계 예제 구현 계획 (보관용)

> 이 문서는 relay 예제를 구현하기 전에 작성한 계획 기록입니다. 현재 `main`에는 `relay/` 예제가 이미 구현되어 있으며, 최신 사용법은 `docs/ko/relay-example.md`를 따릅니다.

## 목표

이 저장소에 세 번째 예제를 추가합니다.

1. `clients/python/` — LiteLLM Proxy를 직접 호출하는 Python 예제
2. `clients/java/` — LiteLLM Proxy를 직접 호출하는 Java 예제
3. `relay/` — LiteLLM Python SDK를 감싼 FastAPI + Hypercorn 중계 예제

세 번째 예제의 핵심은, Java가 upstream LiteLLM Proxy를 직접 때리는 대신,
**tool calling처럼 구조화된 계약**으로 relay를 호출하도록 만드는 것입니다.

즉, relay의 외부 계약은 단순 `input` 문자열이 아니라 다음과 같은 구조를 가집니다.

- `tool_name`
- `research_question`
- `context`
- `constraints`
- `deliverable_format`
- `background`
- `stream`

relay 내부에서만 이 구조를 LiteLLM SDK 요청 형식으로 번역합니다.

---

## 현재 저장소 실제 상태 기준 정리

- 현재 `main`에는 직접 호출용 Python/Java 예제가 이미 존재합니다.
- 두 예제 모두 `chat/completions`, `responses`, `background: true`를 지원합니다.
- 문서 작성 시점 snapshot에서는 open issue 0, open PR 0, milestone 0, project item 0 이었습니다.
- 문서 작성 시점 snapshot에서 최근 CI는 성공 상태였습니다.
- 이 계획 문서가 작성되던 시점에는 `relay/` 예제가 아직 구현되어 있지 않았습니다.

따라서 현재 repository에서 가장 먼저 닫아야 할 canonical task는:

> **세 번째 relay 예제를 위한 repository-local 구현 계획을 만들고, 저장소 구조/검증/계약을 명확히 고정하는 것**

입니다.

---

## 아키텍처 개요

전체 흐름은 다음과 같습니다.

`Azure OpenAI o3-deep-research`
→ `LiteLLM Proxy (Azure Landing Zone)`
→ `LiteLLM Python SDK + FastAPI + Hypercorn relay`
→ `Java caller`

중요한 점은 다음과 같습니다.

- relay는 다시 LiteLLM Proxy를 HTTP로 그대로 재노출하는 서버가 아닙니다.
- relay는 LiteLLM **Python SDK를 wrapping** 합니다.
- Java는 relay에 **구조화된 tool invocation 요청**을 보냅니다.
- relay만 upstream LiteLLM 호출 형식을 압니다.

즉,

- Java ↔ relay 사이: 도메인 지향 / tool-calling-like contract
- relay ↔ LiteLLM SDK 사이: SDK/HTTP 세부 구현

으로 분리합니다.

---

## 최종적으로 추가될 디렉터리와 파일

### 새로 생길 상위 예제

- `relay/`

### relay 내부 주요 파일

- `relay/pyproject.toml`
- `relay/README.md`
- `relay/src/litellm_relay/__init__.py`
- `relay/src/litellm_relay/config.py`
- `relay/src/litellm_relay/contracts.py`
- `relay/src/litellm_relay/upstream.py`
- `relay/src/litellm_relay/service.py`
- `relay/src/litellm_relay/app.py`
- `relay/src/litellm_relay/__main__.py`

### relay 테스트 파일

- `relay/tests/test_config.py`
- `relay/tests/test_contracts.py`
- `relay/tests/test_upstream.py`
- `relay/tests/test_app.py`
- `relay/tests/test_lifecycle.py`

### 기존 예제에서 수정될 가능성이 높은 파일

- `clients/java/src/main/java/example/litellm/Main.java`
- `clients/java/src/main/java/example/litellm/relay/RelayClient.java`
- `clients/java/src/test/java/example/litellm/RelayClientTest.java`
- `clients/java/README.md`

### 저장소 공통 문서/CI 수정 대상

- `.github/workflows/ci.yml`
- `README.md`
- `ARCHITECTURE.md`
- `AGENTS.md`
- `docs/engineering/acceptance-criteria.md`
- `docs/engineering/harness-engineering.md`
- `docs/ko/manual.md`
- `docs/workflow/one-day-delivery-plan.md`

---

## 공개 API 계약 초안

relay는 REST 자원 스타일로 설계합니다.

### 1) Tool invocation 생성

`POST /api/v1/tool-invocations`

요청 예시:

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "Azure OpenAI o3-deep-research relay 구조를 설명해줘",
    "context": ["Azure Landing Zone", "LiteLLM Proxy"],
    "constraints": ["markdown 형식", "보안 가정 포함"],
    "deliverable_format": "markdown_brief",
    "require_citations": true,
    "background": true,
    "stream": false
  }
}
```

### 2) Invocation 상태 조회

`GET /api/v1/tool-invocations/{invocation_id}`

### 3) 완료까지 대기

`GET /api/v1/tool-invocations/{invocation_id}/wait`

### 4) 이벤트 스트림 구독

`GET /api/v1/tool-invocations/{invocation_id}/events`

이렇게 하면 Java 입장에서는:

- "deep_research라는 도구를 호출한다"
- "그 도구에 구조화된 arguments를 넘긴다"

라는 모델로 이해할 수 있고,
relay 내부에서만 LiteLLM SDK 요청으로 바뀝니다.

---

## 단계별 구현 계획

### 1단계: relay scaffold + 설정 로딩

목표:

- `relay/` 패키지 생성
- Hypercorn 진입점 생성
- 기존 저장소 정책과 같은 설정 방식 적용

설정 키:

- `LITELLM_BASE_URL`
- `LITELLM_API_KEY`
- `LITELLM_MODEL` (기본 `o3-deep-research`)
- `RELAY_HOST` (기본 `127.0.0.1`)
- `RELAY_PORT` (기본 `8080`)
- `RELAY_TIMEOUT_SECONDS` (기본 `30`)

정책:

- 실제 환경변수 우선
- `~/.env` fallback 허용
- 프로젝트 로컬 `.env` 자동 로드 금지

테스트:

- `relay/tests/test_config.py`

---

### 2단계: tool-calling-like contract 정의

목표:

- relay 외부 계약을 도메인 지향적으로 고정

핵심 모델 예시:

```python
class DeepResearchArguments(BaseModel):
    research_question: str
    context: list[str] = []
    constraints: list[str] = []
    deliverable_format: Literal[
        "markdown_brief",
        "markdown_report",
        "json_outline",
    ]
    require_citations: bool = True
    background: bool = False
    stream: bool = False

class ToolInvocationRequest(BaseModel):
    tool_name: Literal["deep_research"]
    arguments: DeepResearchArguments
```

테스트:

- `relay/tests/test_contracts.py`

---

### 3단계: LiteLLM SDK adapter 추가

목표:

- relay 내부에서만 LiteLLM SDK 호출 세부 구현 보유

핵심 역할:

- structured arguments → LiteLLM SDK 호출 payload 변환
- foreground responses 호출
- background responses 제출
- response id 조회
- polling
- stream 처리

중요한 원칙:

- relay 외부에는 raw `input` 파라미터를 공개하지 않음
- relay 내부에서만 LiteLLM SDK가 요구하는 형식으로 변환

테스트:

- `relay/tests/test_upstream.py`

---

### 4단계: FastAPI 엔드포인트 구현

목표:

- Java가 relay를 일반 HTTP API처럼 호출 가능하게 만들기

동작 규칙:

- foreground 호출 → 최종 텍스트 결과 반환
- background 호출 → invocation id + upstream response id + 상태 메타데이터 반환
- wait 호출 → polling 후 최종 텍스트 반환
- events 호출 → SSE 이벤트 스트림 반환

테스트:

- `relay/tests/test_app.py`

---

### 5단계: lifecycle (조회 / polling / stream) 구현

목표:

- background와 stream을 실제로 usable한 형태로 닫기

포함 범위:

- upstream `response_id` 조회
- timeout 포함 polling
- 텍스트 중심 SSE relay

간소화 원칙:

- 1차 버전에서는 텍스트 delta만 relay
- 복잡한 전체 event taxonomy는 과도하게 확장하지 않음
- 메타데이터는 보존
- 로그/에러에서 비밀값 노출 금지

테스트:

- `relay/tests/test_lifecycle.py`

---

### 6단계: Java relay caller 추가

목표:

- Java가 직접 LiteLLM Proxy를 호출하는 모드와
- relay를 호출하는 모드를 둘 다 가지게 하기

추가 파일:

- `clients/java/src/main/java/example/litellm/relay/RelayClient.java`
- `clients/java/src/test/java/example/litellm/RelayClientTest.java`

수정 파일:

- `clients/java/src/main/java/example/litellm/Main.java`

예상 역할:

- structured JSON 작성
- relay POST 호출
- background/wait/events 흐름 지원

테스트:

- `mvn -Dtest=RelayClientTest test`

---

### 7단계: 문서와 CI 갱신

목표:

- relay 예제가 저장소의 정식 세 번째 예제로 반영되도록 canonical docs와 CI를 갱신

필수 수정 항목:

- `.github/workflows/ci.yml`에 relay 테스트 추가
- `README.md`에 세 번째 예제 설명 추가
- `ARCHITECTURE.md`에 relay 구조 반영
- `AGENTS.md`에 relay setup/test 명령 추가
- `docs/engineering/acceptance-criteria.md`에 relay 검증 기준 추가
- `docs/engineering/harness-engineering.md`에 relay harness 설명 추가
- `docs/ko/manual.md`에 relay 사용법 추가

---

## 검증 명령

### relay 테스트

```bash
cd relay
uv sync --all-extras --dev
uv run pytest
```

### 기존 Python 예제 테스트

```bash
cd clients/python
uv run pytest
```

### 기존 Java 예제 테스트

```bash
cd clients/java
mvn test
```

### relay 실행 확인

```bash
cd relay
uv run python -m litellm_relay
```

### relay 직접 호출 확인 예시

```bash
curl -X POST http://127.0.0.1:8080/api/v1/tool-invocations \
  -H "Content-Type: application/json" \
  -d '{
    "tool_name": "deep_research",
    "arguments": {
      "research_question": "relay architecture를 요약해줘",
      "deliverable_format": "markdown_brief",
      "background": false,
      "stream": false
    }
  }'
```

### Java → relay 호출 검증

relay caller가 구현되면 다음 형태의 검증을 수행합니다.

```bash
cd clients/java
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay relay architecture를 설명해줘"
```

---

## 위험 요소와 가정

1. upstream LiteLLM Proxy의 `responses`, `background`, `stream` 지원 수준은 Azure OpenAI 배치 구성에 따라 차이가 있을 수 있습니다.
2. relay는 외부에 `input`을 숨기지만, 내부적으로는 여전히 LiteLLM SDK 요청 형식으로 번역해야 합니다.
3. stream은 1차 버전에서 텍스트 delta 중심으로 제한하는 것이 적절합니다.
4. Hypercorn은 이 relay 예제의 기본 ASGI 서버로 채택합니다.
5. 이 예제는 production orchestration 플랫폼이 아니라, **구조와 중계 패턴을 보여주는 예제**여야 합니다.

---

## 완료 기준

이 relay 계획이 실제 구현으로 닫혔다고 판단하려면 최소한 다음이 충족되어야 합니다.

- direct Python 예제 green
- direct Java 예제 green
- relay 테스트 green
- relay CI 포함
- relay 문서화 완료
- Java → relay structured contract 확인
- background / polling / stream 경로 검증 완료
- 관련 PR/CI/문서 상태가 모두 닫힌 상태

즉, 단순히 설계 문서만 있는 상태가 아니라,
**실제 코드 + 테스트 + CI + 문서 + 런타임 검증**까지 모두 닫혀야 완료입니다.
