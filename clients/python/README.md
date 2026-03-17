## Python client

This directory contains a small Python client that calls a LiteLLM-compatible
REST API using the OpenAI-compatible `chat/completions` and `responses`
endpoints to reach the `o3-deep-research` model.

Configuration is read from environment variables, with an optional
`~/.env` file as a fallback:

- `LITELLM_API_KEY` – API key for your LiteLLM proxy
- `LITELLM_BASE_URL` – base URL of the LiteLLM proxy (e.g. `https://localhost:4000` or `https://localhost:4000/v1`)
- `LITELLM_MODEL` (optional) – overrides the default model `o3-deep-research`

### Quickstart

Install dependencies and run tests:

```bash
cd clients/python
uv sync --all-extras --dev
uv run pytest
```

Run the example CLI (requires valid environment variables):

```bash
cd clients/python
uv run python -m litellm_example "Summarize the purpose of the o3-deep-research model."
uv run python -m litellm_example --api responses "Summarize the purpose of the o3-deep-research model."
```
