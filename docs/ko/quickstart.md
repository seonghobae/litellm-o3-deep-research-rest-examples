# 시작하기

## 1. 필요한 값

다음 환경 변수가 필요합니다.

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택, 기본값 `o3-deep-research`)

권장 방식은 홈 디렉터리의 `~/.env` 파일입니다.

```dotenv
LITELLM_API_KEY=sk-your-lite-llm-api-key
LITELLM_BASE_URL=https://localhost:4000/v1
LITELLM_MODEL=o3-deep-research
```

## 2. Python 예제 시작

```bash
cd clients/python
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_example "Reply with exactly: OK"
```

`o3-deep-research`처럼 응답이 느린 모델을 직접 호출할 때는 `--timeout`(초 단위)을 늘리세요.

```bash
uv run python -m litellm_example --timeout 300 "짜장면의 역사를 조사해줘"
```

## 3. Java 예제 시작

```bash
cd clients/java
mvn test
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
```

긴 응답 시간이 예상될 때:

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--timeout 300 짜장면의 역사를 조사해줘"
```

## 4. Relay 예제 시작

터미널 A:

```bash
cd relay
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_relay
```

터미널 B:

```bash
cd clients/java
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--target relay Summarize relay architecture"
```

relay 호출도 `--timeout`을 지원합니다:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 300 짜장면의 역사를 조사해줘"
```

## 5. base URL 규칙

다음 두 형태를 지원합니다.

- `https://localhost:4000`
- `https://localhost:4000/v1`

direct Python/Java 예제는 내부적으로 `/v1/` 루트로 정규화합니다. relay 예제는 같은 값을 LiteLLM SDK의 `api_base`로 그대로 사용하므로, upstream LiteLLM Proxy가 허용하는 root URL 또는 `/v1` URL을 넣으면 됩니다.

## 6. 무엇이 이미 구현되어 있나

- Python 직접 호출 예제
- Java 직접 호출 예제
- LiteLLM SDK + FastAPI + Hypercorn relay 예제
- `responses` + `background: true` 지원
- relay의 structured tool invocation + status/wait/events API
- 한국어 매뉴얼 및 GitHub Pages 문서 구조
