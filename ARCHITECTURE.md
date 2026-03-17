# Architecture

This repository is intentionally small and split by language under `clients/`.

## Structure
- `clients/python/`: Python example package, CLI entrypoint, and pytest suite.
- `clients/java/`: Java 21 example application, Maven build, and JUnit suite.
- `docs/`: repository-specific contributor guidance, acceptance criteria, and workflow notes.
- `.github/workflows/`: CI that verifies both example clients.

## Design choices
- Both clients support the OpenAI-compatible `POST /v1/chat/completions` and `POST /v1/responses` endpoints.
- Both clients accept `LITELLM_BASE_URL` as either the proxy root or `/v1`, and normalise it to a predictable `/v1/` API base.
- Both clients load `LITELLM_API_KEY` and `LITELLM_BASE_URL` from the process environment, with `~/.env` as an optional fallback for local development.
- The examples focus on synchronous text-generation paths and explicit error handling; streaming and tool-calling are intentionally out of scope.
