# Harness engineering

This repository uses lightweight local harnesses instead of external test services.

## Python

- Tests stub `urllib.request.urlopen` so request construction and response parsing can be verified without a live server for both `chat/completions` and `responses`.
- Background `responses` tests verify that `background: true` is sent and that raw response metadata is preserved for callers.
- Live verification is done separately by running the CLI against the configured LiteLLM endpoint.

## Java

- Tests use JDK `HttpServer` to emulate `POST /v1/chat/completions` and `POST /v1/responses` with success and error payloads.
- Background `responses` tests verify the request flag and JSON metadata handling.
- Live verification is done separately by invoking the `Main` class via Maven.

## Relay

- Relay tests keep the LiteLLM SDK offline by monkeypatching `litellm.responses`, `litellm.aresponses`, and `litellm.aget_responses` in unit tests.
- FastAPI endpoint tests use `TestClient` against an in-memory `RelayService` with fake gateway implementations.
- Lifecycle tests verify background polling and text-only SSE relay semantics without a live upstream service.
- Live verification is done separately by starting Hypercorn locally and pointing the relay at either a configured LiteLLM Proxy or a local fake upstream.

## Safety rules

- Keep tests deterministic and offline by default.
- Never capture live credentials in fixtures, logs, or committed artifacts.
- Keep relay streaming tests text-focused; do not expand them into full vendor-specific event taxonomies unless the example contract changes.
