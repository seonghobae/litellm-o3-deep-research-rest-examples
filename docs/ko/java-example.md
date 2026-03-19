# Java 직접 호출 예제

## 위치

- `clients/java/`

## 지원 범위

- `POST /v1/chat/completions`
- `POST /v1/responses`
- `POST /v1/responses` + `background: true`

## 테스트

```bash
cd clients/java
mvn test
```

## foreground chat/completions 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
```

## foreground responses 호출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
```

## background responses 제출

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

## 타임아웃 조정 (--timeout)

기본 타임아웃은 30초입니다. `o3-deep-research`처럼 응답 시간이 긴 모델을 사용할 때는 `--timeout <초>`로 늘리세요.

```bash
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--timeout 300 짜장면의 역사를 상세히 조사해줘"
```

relay 호출에도 동일하게 적용됩니다:

```bash
RELAY_BASE_URL=http://127.0.0.1:8080 \
mvn -q exec:java -Dexec.mainClass=example.litellm.Main \
  -Dexec.args="--target relay --timeout 300 짜장면의 역사를 조사해줘"
```

## 해석 포인트

- Java도 Python과 같은 API 흐름을 지원합니다.
- background 모드에서는 원본 JSON 메타데이터를 반환합니다.
- `--timeout`: 모델 응답 대기 시간 (초). 기본값 30초. 직접 호출과 relay 모두 지원
- 현재 Java 예제 역시 상시 서비스가 아니라 1회성 CLI입니다.
- relay를 호출하려면 `--target relay`를 사용하고, 자세한 내용은 [Relay 중계 예제](relay-example.md)를 참고하세요.
