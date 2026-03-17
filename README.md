## LiteLLM o3-deep-research REST examples

This repository contains minimal Python and Java example clients that call a
LiteLLM-compatible REST API using the OpenAI-compatible `chat/completions` and
`responses` endpoints to reach the `o3-deep-research` model.

Both clients are configured via environment variables and an optional
`~/.env` file:

- `LITELLM_API_KEY` – API key for your LiteLLM proxy
- `LITELLM_BASE_URL` – base URL of the LiteLLM proxy (e.g. `https://localhost:4000` or `https://localhost:4000/v1`)
- `LITELLM_MODEL` (optional) – overrides the default model `o3-deep-research`

The examples are designed to be safe for public repositories:

- No secrets are committed – use `.env.example` as a template only.
- Tests run against mocked HTTP servers by default.
- Live calls to a real LiteLLM deployment are opt-in and should only be run in
  environments where `LITELLM_API_KEY` and `LITELLM_BASE_URL` are set.

## Repository layout

- `clients/python/` – Python package, CLI entrypoint, and pytest suite
- `clients/java/` – Java 21 application, Maven build, and JUnit suite
- `docs/` – repository-specific workflow, acceptance, and security guidance

## Quickstart

### Python

```bash
cd clients/python
uv sync --all-extras --dev
uv run pytest
uv run python -m litellm_example "Reply with exactly: OK"
uv run python -m litellm_example --api responses "Reply with exactly: OK"
uv run python -m litellm_example --api responses --background "Reply with exactly: OK"
```

### Java

```bash
cd clients/java
mvn test
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses Reply with exactly: OK"
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="--api responses --background Reply with exactly: OK"
```

## Environment setup

Create `~/.env` (or export variables in your shell) with:

```dotenv
LITELLM_API_KEY=sk-your-lite-llm-api-key
LITELLM_BASE_URL=https://localhost:4000/v1
LITELLM_MODEL=o3-deep-research
```

The clients accept either a proxy root URL such as `https://localhost:4000` or
an explicit `/v1` root such as `https://localhost:4000/v1`.

## Korean manual

- 한국어 매뉴얼: `docs/ko/manual.md`
