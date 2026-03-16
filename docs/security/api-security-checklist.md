# API security checklist

Apply this checklist to both clients and any future API examples:

1. Require `Authorization: Bearer <key>` on outbound requests.
2. Validate that `LITELLM_BASE_URL` includes a scheme and host; reject ambiguous endpoint paths.
3. Send `Content-Type: application/json` and `Accept: application/json`.
4. Never log or print API keys.
5. Surface non-2xx status codes with safe, human-readable error messages.
6. Keep offline tests free of live credentials or captured traffic.
