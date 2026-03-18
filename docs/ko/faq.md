# FAQ

## 이 저장소는 무엇을 보여주나요?

LiteLLM Proxy를 통해 `o3-deep-research`를 호출하는 Python 직접 예제, Java 직접/relay 호출 예제, 그리고 FastAPI + Hypercorn relay 서버 예제를 보여줍니다.

## 지금 relay 예제가 이미 구현되어 있나요?

네. `relay/` 아래에 구현되어 있고, Java에서는 `--target relay` 모드로 호출할 수 있습니다.

## background 요청을 보내면 클라이언트가 daemon처럼 계속 떠 있나요?

아니요. direct Python/Java 예제는 foreground 1회성 CLI이지만, `relay/` 예제는 FastAPI + Hypercorn으로 실행되는 장기 실행 서버입니다.

## GitHub Pages로 볼 수 있게 되어 있나요?

네. GitHub Pages workflow가 성공하면 `github.io` 주소에서 한국어 문서를 읽을 수 있습니다.

## 왜 relay 예제에서 `input` 대신 tool-calling-like 구조를 쓰나요?

Java 호출자에게 upstream LiteLLM 세부 구현을 숨기고,
중계 서버가 도메인 지향 계약을 제공하게 하기 위해서입니다.
