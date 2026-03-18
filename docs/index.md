# LiteLLM o3-deep-research 예제 문서

이 사이트는 구현된 두 가지 직접 호출 예제와, 후속으로 추가할 중계 예제 계획을 한국어로 안내합니다.

1. **Python 직접 호출 예제**
2. **Java 직접 호출 예제**
3. **LiteLLM SDK + FastAPI + Hypercorn 중계 예제 계획**

## 이 저장소에서 할 수 있는 것

- LiteLLM Proxy를 통해 `o3-deep-research` 모델 호출
- `chat/completions` 와 `responses` API 비교
- `background: true` 제출 방식 이해
- Java 호출자를 위한 relay/tool-calling 구조 계획 확인

## 문서 읽는 순서

처음 보는 사용자에게는 다음 순서를 권장합니다.

1. [시작하기](ko/quickstart.md)
2. [Python 직접 호출](ko/python-example.md)
3. [Java 직접 호출](ko/java-example.md)
4. [Responses / Background / 중계 계획의 스트리밍](ko/responses-guide.md)
5. [중계 예제 구현 계획](ko/relay-toolcalling-plan.md)

## 빠른 사실 확인

- 현재 구현 완료: Python 직접 호출, Java 직접 호출
- 현재 계획 완료: relay 예제 설계 문서화
- 현재 문서 사이트: GitHub Pages 배포 가능 구조

## 저장소 링크

- GitHub 저장소: <https://github.com/seonghobae/litellm-o3-deep-research-rest-examples>
