# FAQ

## 이 저장소는 무엇을 보여주나요?

LiteLLM Proxy를 통해 `o3-deep-research`를 호출하는 Python/Java 예제와,
향후 추가될 relay 예제의 구현 계획을 보여줍니다.

## 지금 relay 예제가 이미 구현되어 있나요?

아직 아닙니다. 현재는 repository-local 구현 계획 문서까지 완료된 상태입니다.

## background 요청을 보내면 클라이언트가 daemon처럼 계속 떠 있나요?

아니요. 현재 예제들은 모두 foreground 1회성 CLI입니다.

## GitHub Pages로 볼 수 있게 되어 있나요?

이 브랜치 작업에서는 GitHub Pages 배포 구조를 추가합니다. 배포 workflow가 성공하면
`github.io` 주소에서 한국어 문서를 읽을 수 있게 됩니다.

## 왜 relay 예제에서 `input` 대신 tool-calling-like 구조를 쓰나요?

Java 호출자에게 upstream LiteLLM 세부 구현을 숨기고,
중계 서버가 도메인 지향 계약을 제공하게 하기 위해서입니다.
