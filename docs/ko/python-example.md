# Python 직접 호출 예제

## 위치

- `clients/python/`

## 지원 범위

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/responses` + `background: true`

## 테스트

```bash
cd clients/python
uv run pytest
```

## foreground chat/completions 호출

```bash
uv run python -m litellm_example "Reply with exactly: OK"
```

## foreground responses 호출

```bash
uv run python -m litellm_example --api responses "Reply with exactly: OK"
```

## background responses 제출

```bash
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
```

이 경우 최종 텍스트 대신 원본 JSON 메타데이터를 출력합니다.

## 타임아웃 조정 (--timeout)

기본 타임아웃은 30초입니다. `o3-deep-research`처럼 응답 시간이 긴 모델을 사용할 때는 `--timeout <초>`로 늘리세요.

```bash
uv run python -m litellm_example --timeout 300 "짜장면의 역사를 상세히 조사해줘"
uv run python -m litellm_example --api responses --timeout 300 "짜장면의 역사를 상세히 조사해줘"
```

## 해석 포인트

- foreground 호출: 바로 읽을 수 있는 텍스트를 반환
- background 호출: `id`, `status` 같은 메타데이터 중심 응답
- `--timeout`: 모델 응답 대기 시간 (초). 기본값 30초
- 현재 Python 예제는 상시 실행 서버가 아니라 1회성 CLI입니다.
