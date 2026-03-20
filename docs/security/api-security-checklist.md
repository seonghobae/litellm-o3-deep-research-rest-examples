# API security checklist

Apply this checklist to both clients and any future API examples:

1. Require `Authorization: Bearer <key>` on outbound requests.
2. Validate that `LITELLM_BASE_URL` includes a scheme and host; reject ambiguous endpoint paths.
3. Send `Content-Type: application/json` and `Accept: application/json`.
4. Never log or print API keys.
5. Surface non-2xx status codes with safe, human-readable error messages.
6. relay 오류 payload나 SSE error event에 upstream 원문 예외, 호스트명, SDK/provider 내부 정보를 노출하지 않는다.
7. 오프라인 테스트에는 실제 자격 증명이나 캡처된 운영 트래픽을 포함하지 않는다.
