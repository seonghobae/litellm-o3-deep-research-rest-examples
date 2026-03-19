# FAQ

## 이 저장소는 무엇을 보여주나요?

LiteLLM Proxy를 통해 `o3-deep-research`를 호출하는 Python 직접 예제, Java 직접/relay 호출 예제, 그리고 FastAPI + Hypercorn relay 서버 예제를 보여줍니다. 또한 web_search_preview, system_prompt, text_format, 자동 tool calling 등 고급 기능들도 모두 포함되어 있습니다.

## 지금 relay 예제가 이미 구현되어 있나요?

네. `relay/` 아래에 구현되어 있고, Java에서는 `--target relay` 모드로 호출할 수 있습니다. relay는 foreground, background, stream 세 가지 모드를 지원하며, 자동 tool calling을 위한 `POST /api/v1/chat` 엔드포인트도 포함합니다.

## background 요청을 보내면 클라이언트가 daemon처럼 계속 떠 있나요?

아니요. direct Python/Java 예제는 foreground 1회성 CLI이지만, `relay/` 예제는 FastAPI + Hypercorn으로 실행되는 장기 실행 서버입니다.

## GitHub Pages로 볼 수 있게 되어 있나요?

네. `main` 브랜치 push 또는 GitHub Actions의 수동 실행(`workflow_dispatch`) 시 GitHub Pages에 배포됩니다. [`seonghobae.github.io/litellm-o3-deep-research-rest-examples`](https://seonghobae.github.io/litellm-o3-deep-research-rest-examples)에서 한국어 문서를 읽을 수 있습니다.

## 왜 relay 예제에서 `input` 대신 tool-calling-like 구조를 쓰나요?

Java 호출자에게 upstream LiteLLM 세부 구현을 숨기고, 중계 서버가 도메인 지향 계약을 제공하게 하기 위해서입니다. `research_question`, `deliverable_format` 등의 구조화된 인자를 사용하면 upstream API 변경에 영향받지 않고 relay contract를 안정적으로 유지할 수 있습니다.

## --web-search 플래그는 언제 쓰나요?

`gpt-4o` 같은 일반 모델에서 최신 정보가 필요할 때 사용합니다. `--api responses`와 함께만 사용 가능합니다. `o3-deep-research`는 자체적으로 심층 조사를 수행하므로 이 플래그가 불필요합니다.

```bash
LITELLM_MODEL=gpt-4o \
uv run python -m litellm_example --api responses --web-search --timeout 60 "최신 AI 뉴스"
```

## --auto-tool-call 은 어떻게 동작하나요?

모델(gpt-4o)이 스스로 "이 질문은 deep_research가 필요하다"고 판단하면 relay를 통해 deep_research를 자동으로 실행하고, 결과로 최종 답변을 합성합니다. relay 서버가 실행 중이어야 합니다.

```bash
# relay 서버 시작
cd relay && uv run python -m litellm_relay

# Python --auto-tool-call
LITELLM_MODEL=gpt-4o RELAY_BASE_URL=http://127.0.0.1:8080 \
uv run python -m litellm_example --auto-tool-call --timeout 300 "짜장면의 역사를 조사해줘"
```

## system_prompt 는 무엇이고 어떻게 쓰나요?

relay의 `DeepResearchArguments.system_prompt`는 Responses API의 `instructions` 필드로 전달됩니다. 페르소나 주입, 출력 언어 강제, 형식 제약 등 모델 수준 지시문에 사용합니다.

```json
{
  "tool_name": "deep_research",
  "arguments": {
    "research_question": "짜장면의 역사를 설명해줘",
    "deliverable_format": "markdown_brief",
    "system_prompt": "You are a food historian. Always answer in English only."
  }
}
```

## text_format 은 무엇인가요?

relay의 `arguments.text_format`은 Responses API의 `text.format`에 매핑됩니다. `gpt-4o` 같은 호환 모델에서는 JSON 출력을 강하게 제어할 수 있습니다. `o3-deep-research`는 `json_schema`를 API 400으로 거부하고, `json_object`는 API 레벨에서 수용될 수 있지만 실제 JSON object 준수는 보장되지 않습니다.

```json
{
  "arguments": {
    "research_question": "...",
    "deliverable_format": "json_outline",
    "text_format": {"type": "json_object"}
  }
}
```

## RELAY_RESEARCH_TIMEOUT_SECONDS 는 왜 필요한가요?

`/api/v1/chat` 자동 tool calling에서 two-stage 타임아웃을 사용합니다. Chat Completions 턴(30초 기본)과 deep_research 실행(300초 기본)을 분리했습니다. `o3-deep-research`는 최대 10분 이상 걸릴 수 있으므로 필요시 `RELAY_RESEARCH_TIMEOUT_SECONDS=600`으로 늘리세요.

## o3-deep-research 외에 다른 모델도 사용할 수 있나요?

네. `LITELLM_MODEL` 환경변수로 지정하면 됩니다. `gpt-4o` 등 다른 모델도 모두 지원합니다. 단, `o3-deep-research`는 자체 심층 조사 기능을 포함한 특수 모델이므로 일반 모델과 다른 특성을 가집니다. 자동 tool calling의 orchestration 모델은 `LITELLM_CHAT_MODEL`(기본 `gpt-4o`)으로 따로 지정합니다.

## 테스트 커버리지 기준은 무엇인가요?

- Python relay: 100% (pytest-cov `--cov-fail-under=100`)
- Python client: 100% (pytest-cov `--cov-fail-under=100`)
- Java: BUILD SUCCESS (JaCoCo 포함)

모든 기능(system_prompt, text_format, web_search, auto_tool_call, ChatOrchestrator 타임아웃 분리, 예외 처리 등)이 테스트로 검증됩니다.
