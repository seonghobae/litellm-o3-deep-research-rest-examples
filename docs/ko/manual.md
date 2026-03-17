# LiteLLM o3-deep-research 한국어 매뉴얼

이 저장소는 `o3-deep-research` 모델을 LiteLLM 호환 REST API로 호출하는
예제를 제공합니다. Python과 Java 두 가지 구현이 들어 있으며, 둘 다
OpenAI 호환 API 스타일인 다음 두 가지를 지원합니다.

- `POST /v1/chat/completions`
- `POST /v1/responses`

## 1. 무엇을 하는 저장소인가요?

- LiteLLM 프록시 뒤에 있는 `o3-deep-research` 모델을 호출하는 최소 예제입니다.
- Python 예제는 `clients/python/`에 있습니다.
- Java 예제는 `clients/java/`에 있습니다.
- 테스트는 실제 서버 없이도 돌아가도록 기본적으로 mock/local harness를 사용합니다.
- 실제 LiteLLM 서버가 있으면, 동일한 예제 명령으로 실호출 검증도 할 수 있습니다.

## 2. 사전 준비

다음 값이 필요합니다.

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택 사항, 기본값은 `o3-deep-research`)

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

내부적으로는 `/v1/` API 루트로 정규화해서 사용합니다.

보안상 Python 예제는 원격 호스트에 대해 평문 `http://`를 허용하지 않습니다.
즉, 로컬 개발(`localhost`, `127.0.0.1`)이 아닌 경우에는 `https://`를 써야 합니다.

## 3. Python 사용 방법

경로:

```bash
cd clients/python
```

### 의존성 설치 및 테스트

```bash
uv sync --all-extras --dev
uv run pytest
```

### 3-1. chat/completions API 호출

```bash
uv run python -m litellm_example "Reply with exactly: OK"
```

이 명령은 내부적으로 다음 계열 호출을 수행합니다.

- `POST /v1/chat/completions`

요청 형태는 대략 다음과 같습니다.

```json
{
  "model": "o3-deep-research",
  "messages": [
    {"role": "user", "content": "Reply with exactly: OK"}
  ]
}
```

### 3-2. responses API 호출

```bash
uv run python -m litellm_example --api responses "Reply with exactly: OK"
```

이 명령은 내부적으로 다음 계열 호출을 수행합니다.

- `POST /v1/responses`

요청 형태는 대략 다음과 같습니다.

```json
{
  "model": "o3-deep-research",
  "input": "Reply with exactly: OK"
}
```

### 3-3. responses API를 background 모드로 제출

```bash
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
```

이 경우 요청 바디에 다음 값이 추가됩니다.

```json
{
  "model": "o3-deep-research",
  "input": "Reply with exactly: OK",
  "background": true
}
```

이 모드에서는 완성된 텍스트만 뽑아내는 대신, LiteLLM/OpenAI 호환 Responses API가
돌려준 **원본 JSON 응답**을 그대로 출력합니다. 이유는 background 작업에서는
즉시 최종 텍스트 대신 `id`, `status` 같은 메타데이터가 더 중요하기 때문입니다.

## 4. Java 사용 방법

경로:

```bash
cd clients/java
```

### 빌드 및 테스트

```bash
mvn test
```

### 4-1. chat/completions API 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
```

### 4-2. responses API 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
```

### 4-3. responses API를 background 모드로 제출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

Java 예제도 Python과 동일하게 다음 두 경로를 지원합니다.

- `POST /v1/chat/completions`
- `POST /v1/responses`

## 5. 그러면 이게 background 설정이 되나요?

정확히 말하면 **두 가지 의미를 구분해야 합니다.**

### 5-1. 프로세스 자체가 background 서비스인가?

아니요. **현재 예제는 background 서비스가 아니라 foreground 1회성 CLI**입니다.

의미를 정확히 설명하면:

- 명령을 실행하면
- 요청 1건을 LiteLLM에 보내고
- 응답을 출력한 뒤
- 프로세스가 종료됩니다.

즉, 현재 상태는 다음과 같습니다.

- 데몬(daemon) 아님
- 서버(server) 아님
- 지속 실행(worker) 아님
- systemd/launchd/supervisord 설정 포함 안 됨

### 5-2. Responses API 요청 자체를 background 모드로 보낼 수 있나?

네. **가능합니다.**

LiteLLM/OpenAI 호환 Responses API 쪽에는 `background: true` 요청 인자를 줄 수 있고,
이 저장소의 현재 예제도 이제 그 값을 전달할 수 있습니다.

즉:

- CLI 프로세스는 여전히 실행 후 종료되는 foreground 도구이지만
- 서버에 보내는 **Responses API 작업 자체는 background 모드로 제출**할 수 있습니다.

정리하면:

- **클라이언트 프로세스**는 background 서비스 아님
- **Responses API 작업**은 `background: true`로 background 실행 요청 가능

### background 실행이 필요한 경우

현재 저장소는 **상시 떠 있는 background 서비스 모드**는 기본 제공하지 않습니다.

다만 다음과 같은 방식으로 감쌀 수는 있습니다.

- `nohup ... &`
- `tmux` / `screen`
- macOS `launchd`
- Linux `systemd`
- 별도의 스크립트로 주기 실행(cron)

하지만 이 경우에도 본질은 “지속적으로 떠 있는 API 서버”가 아니라,
**CLI를 외부 도구로 백그라운드에서 실행하는 것**입니다.

만약 진짜 background 용도로 쓰려면 별도 구현이 필요합니다. 예를 들어:

- 프롬프트를 큐에서 읽는 worker 모드
- HTTP 서버 모드
- 배치 파일을 읽어 순차 처리하는 daemon 모드

현재 저장소에는 그런 기능이 포함되어 있지 않습니다.

## 6. 문제 해결

### 6-1. `LITELLM_API_KEY is not set`

원인:

- 환경변수가 없거나
- `~/.env` 파일이 없거나
- 값이 비어 있음

확인:

```bash
echo "$LITELLM_API_KEY"
cat ~/.env
```

### 6-2. `LITELLM_BASE_URL is not set`

원인:

- `LITELLM_BASE_URL`이 설정되지 않음

예시:

```dotenv
LITELLM_BASE_URL=https://your-litellm-host/v1
```

### 6-3. SSL / 인증서 오류

Python에서 원격 서버 인증서 문제로 SSL 오류가 날 수 있습니다.

이 저장소의 Python 예제는 `certifi` CA 번들을 사용합니다. 그래도 실패하면:

- LiteLLM 프록시 인증서 체인이 정상인지 확인
- 사설 인증서라면 신뢰 저장소 구성이 필요한지 확인

### 6-4. 4xx / 5xx 응답

점검 항목:

- API 키가 맞는지
- 모델 이름(`o3-deep-research`)이 실제 LiteLLM 설정에서 허용되는지
- 프록시가 `/v1/chat/completions` 또는 `/v1/responses`를 노출하는지
- background 응답이라면 반환된 `id`, `status`를 기준으로 후속 조회가 필요한지

### 6-5. 로컬 테스트는 되는데 실호출이 안 되는 경우

기본 테스트는 mock 기반이므로, 네트워크나 인증서 문제는 실제 호출에서만 드러날 수 있습니다.
이 경우 다음 두 가지를 직접 실행해 보세요.

```bash
cd clients/python
uv run python -m litellm_example "Reply with exactly: OK"
uv run python -m litellm_example --api responses "Reply with exactly: OK"
```

```bash
cd clients/java
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
```

## 7. 요약

- 이 저장소는 Python/Java에서 LiteLLM의 두 가지 OpenAI 호환 API 스타일을 예제로 제공합니다.
- `chat/completions`와 `responses`를 둘 다 테스트하고 실제 호출할 수 있습니다.
- `responses`는 `background: true` 요청도 보낼 수 있습니다.
- 설정은 `~/.env` 또는 환경변수로 주입합니다.
- 현재 구현은 **요청 1회 실행 후 종료되는 CLI 도구**이며, 상시 background 서비스는 아닙니다.
- 다만 `responses` 호출은 서버 측 background 작업으로 제출할 수 있습니다.
