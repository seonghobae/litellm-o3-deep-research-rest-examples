# Responses / Background / Relay 스트리밍 정리

## 1. `responses` 와 `chat/completions` 차이

- `chat/completions`: 전통적인 메시지 중심 호출
- `responses`: 더 일반화된 응답 모델

현재 저장소는 두 방식을 모두 예제로 제공합니다.

## 2. `background: true` 의 의미

`background: true` 는 **서버 측 작업 제출 방식**입니다.

즉:

- 로컬 프로세스가 background daemon이 된다는 뜻이 아님
- 서버가 작업을 큐잉/비동기 처리할 수 있게 요청한다는 뜻

## 3. 현재 저장소 기준 해석

- Python/Java 예제는 모두 foreground 1회성 CLI
- 하지만 `responses` 호출은 서버 쪽 background 작업으로 제출 가능

## 4. 스트리밍 상태

현재 `main` 기준 직접 예제는 다음을 보여줍니다.

- foreground `responses`
- background `responses`

하지만 **직접 예제 자체가 stream 이벤트를 소비하는 고급 예제까지 포함하는 것은 아닙니다.**
stream 이벤트 수명주기는 relay 예제에서 구현되어 있으며, relay의 `GET /api/v1/tool-invocations/{id}/events`가 text-only SSE를 제공합니다.

## 5. relay 예제와의 연결

relay 예제는 다음 lifecycle을 정식으로 다룹니다.

- foreground invocation
- background invocation
- polling / wait
- SSE event stream

자세한 내용은 [Relay 중계 예제](relay-example.md)에서 확인할 수 있고, 구현 전 설계 판단은 [중계 예제 구현 계획(보관)](relay-toolcalling-plan.md)에서 볼 수 있습니다.
