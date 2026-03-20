# LiteLLM o3-deep-research 예제 문서

이 사이트는 구현된 세 가지 예제를 한국어로 안내합니다.

1. **Python 직접 호출 예제**
2. **Java 직접 호출 예제**
3. **LiteLLM SDK + FastAPI + Hypercorn 중계 예제**

## 이 저장소에서 할 수 있는 것

- LiteLLM Proxy를 통해 `o3-deep-research` 모델 호출
- `chat/completions` 와 `responses` API 비교
- `background: true` 제출 방식 이해
- Java 호출자를 위한 relay/tool-calling 구조 확인
- `web_search_preview`로 일반 모델에 실시간 웹 검색 추가
- `system_prompt`로 deep research 단계의 페르소나/출력 언어 제어
- `text_format`으로 JSON 출력 강제 (`json_object`, `json_schema`)
- client-side `--auto-tool-call` 과 relay-side `POST /api/v1/chat` 비교
- relay의 chat timeout / research timeout 분리 구조 확인

## 문서 읽는 순서

처음 보는 사용자에게는 다음 순서를 권장합니다.

1. [시작하기](ko/quickstart.md)
2. [Python 직접 호출](ko/python-example.md)
3. [Java 직접 호출](ko/java-example.md)
4. [Relay 중계 예제](ko/relay-example.md)
5. [Responses / Background / Relay 스트리밍](ko/responses-guide.md)
6. [자동 Tool Calling](ko/auto-toolcalling.md)
7. [중계 예제 구현 계획(보관)](ko/relay-toolcalling-plan.md)

## 빠른 사실 확인

- 현재 구현 완료: Python direct, Java direct, relay 중계 예제
- 현재 고급 기능: `--web-search`, `--auto-tool-call`, relay `/api/v1/chat`, `system_prompt`, `text_format`
- 현재 검증 상태: Python/Java/relay 테스트, docs build, GitHub Pages 배포, 라이브 검증 결과까지 문서화

## 핵심 고급 기능

- `web_search_preview`: Python / Java direct client에서 `--api responses --web-search`
- `system_prompt`: relay `deep_research` wrapper에서 Responses API `instructions`로 전달
- `text_format`: relay `deep_research` wrapper에서 JSON 출력 강제 지원
- 자동 tool calling: client-side `--auto-tool-call` 과 relay-side `POST /api/v1/chat` 둘 다 구현

## Relay `/api/v1/chat` 요약

이 저장소의 relay는 일반 대화 요청을 받아 모델이 스스로 `deep_research`를 호출할지 결정하는 `POST /api/v1/chat` 엔드포인트를 제공합니다.

요청 필드:

- `message`
- `context`
- `auto_tool_call`
- `system_prompt`
- `deliverable_format`

응답 필드:

- `content`
- `tool_called`
- `tool_name`
- `research_summary`

자세한 내용은 [자동 Tool Calling](ko/auto-toolcalling.md)과 [Relay 중계 예제](ko/relay-example.md)를 참고하세요.

## Relay 환경 변수

- `RELAY_HOST` — 기본 `127.0.0.1`
- `RELAY_PORT` — 기본 `8080`
- `RELAY_TIMEOUT_SECONDS` — Chat Completions orchestration timeout (기본 `30`)
- `RELAY_RESEARCH_TIMEOUT_SECONDS` — deep_research execution timeout (기본 `300`)
- `LITELLM_CHAT_MODEL` — relay auto tool calling orchestration 모델 (기본 `gpt-4o`)

## 라이브 검증 현황

- direct `chat` / `responses` / `background`
- relay `tool-invocations` foreground / background / stream
- relay `/api/v1/chat` tool/no-tool
- `--web-search`
- `--auto-tool-call`
- `system_prompt`, `deliverable_format`

실제 실행 예시와 결과는 [통합 매뉴얼](ko/manual.md)에서 확인할 수 있습니다.

## 저장소 링크

- GitHub 저장소: <https://github.com/seonghobae/litellm-o3-deep-research-rest-examples>
