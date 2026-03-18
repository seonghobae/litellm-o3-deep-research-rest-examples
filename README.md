## LiteLLM o3-deep-research 예제 저장소

이 저장소는 LiteLLM Proxy를 통해 `o3-deep-research` 모델을 호출하는 예제를 제공합니다.

현재 저장소의 범위는 다음 세 가지입니다.

1. `clients/python/` — Python 직접 호출 예제
2. `clients/java/` — Java 직접 호출 예제
3. `docs/ko/relay-toolcalling-plan.md` — LiteLLM SDK + FastAPI + Hypercorn 중계 예제 계획

즉, **구현 완료된 예제는 Python/Java 두 가지**이고, **세 번째 중계 예제는 현재 계획 문서까지 완료된 상태**입니다.

## 필요한 환경 변수

다음 값을 `~/.env` 또는 현재 셸 환경 변수로 제공하면 됩니다.

- `LITELLM_API_KEY`
- `LITELLM_BASE_URL`
- `LITELLM_MODEL` (선택, 기본값 `o3-deep-research`)

예시:

```dotenv
LITELLM_API_KEY=sk-your-lite-llm-api-key
LITELLM_BASE_URL=https://localhost:4000/v1
LITELLM_MODEL=o3-deep-research
```

`LITELLM_BASE_URL`은 `https://host:4000` 또는 `https://host:4000/v1` 형태를 모두 지원하며, 내부적으로 `/v1/` 루트로 정규화합니다.

## 문서 사이트

이 저장소는 GitHub Pages로 한국어 문서를 출판할 수 있도록 구성됩니다.

- 홈 문서: `docs/index.md`
- 통합 매뉴얼: `docs/ko/manual.md`
- 중계 예제 계획: `docs/ko/relay-toolcalling-plan.md`

예상 Pages URL:

- <https://seonghobae.github.io/litellm-o3-deep-research-rest-examples/>

## 빠른 시작

### Python

```bash
cd clients/python
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_example "Reply with exactly: OK"
uv run python -m litellm_example --api responses "Reply with exactly: OK"
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
```

### Java

```bash
cd clients/java
mvn test
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

## `background: true` 해석

이 저장소의 CLI는 Python/Java 모두 **foreground 1회성 도구**입니다. 하지만 `responses` 호출에 `--background`를 주면, 클라이언트 프로세스를 daemon으로 바꾸는 것이 아니라 **서버 측 Responses 작업을 background 모드로 제출**합니다.

이때 예제는 최종 텍스트 대신 `id`, `status` 같은 후속 추적용 메타데이터가 담긴 원본 JSON 응답을 출력합니다.

## 보안 주의

- 실제 `~/.env` 파일과 API 키는 Git에 커밋하지 마세요.
- 샘플 값이 필요하면 `.env.example`만 사용하세요.

## 문서 빌드 확인

```bash
python3 -m pip install -r requirements-docs.txt
mkdocs build --strict
```
