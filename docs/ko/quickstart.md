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

## 3. Java 예제 시작

```bash
cd clients/java
mvn test
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
```

## 4. base URL 규칙

다음 두 형태를 지원합니다.

- `https://localhost:4000`
- `https://localhost:4000/v1`

내부적으로는 `/v1/` 루트로 정규화합니다.

## 5. 무엇이 이미 구현되어 있나

- Python 직접 호출 예제
- Java 직접 호출 예제
- `responses` + `background: true` 지원
- 한국어 매뉴얼 및 GitHub Pages 문서 구조
- relay 예제는 현재 **구현 계획 문서**까지 완료
