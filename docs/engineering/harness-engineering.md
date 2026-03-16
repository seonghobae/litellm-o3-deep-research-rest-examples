# Harness engineering

This repository uses lightweight local harnesses instead of external test services.

## Python
- Tests stub `urllib.request.urlopen` so request construction and response parsing can be verified without a live server.
- Live verification is done separately by running the CLI against the configured LiteLLM endpoint.

## Java
- Tests use JDK `HttpServer` to emulate `POST /v1/chat/completions` with success and error payloads.
- Live verification is done separately by invoking the `Main` class via Maven.

## Safety rules
- Keep tests deterministic and offline by default.
- Never capture live credentials in fixtures, logs, or committed artifacts.
