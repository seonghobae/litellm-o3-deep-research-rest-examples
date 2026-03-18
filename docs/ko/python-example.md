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

## 해석 포인트

- foreground 호출: 바로 읽을 수 있는 텍스트를 반환
- background 호출: `id`, `status` 같은 메타데이터 중심 응답
- 현재 Python 예제는 상시 실행 서버가 아니라 1회성 CLI입니다.
