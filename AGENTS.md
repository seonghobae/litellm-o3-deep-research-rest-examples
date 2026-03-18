# AGENTS.md

## Project overview
- This repository provides public Python and Java examples for calling a LiteLLM-compatible REST API with the `o3-deep-research` model.
- Repository-specific operating guidance lives in `docs/**` and is authoritative for contributors and agents.

## Setup commands
- Python: `cd clients/python && uv sync --all-extras --dev`
- Java: `cd clients/java && mvn test`
- Docs: `python3 -m pip install -r requirements-docs.txt`

## Build / Test commands
- Python tests: `cd clients/python && uv run pytest`
- Java tests: `cd clients/java && mvn test`
- Docs build: `mkdocs build --strict`

## Code style
- Keep the examples minimal, dependency-light, and explicit about OpenAI-compatible wire format.
- Do not silently read project-local `.env`; the examples use environment variables and optionally `~/.env` only.
- User-facing manuals and published docs should be written in Korean.

## Security considerations
- Never commit secrets or a populated `.env` file.
- Preserve redaction in logs and error output.
- Follow `docs/security/api-security-checklist.md` for API-related changes.

## PR / Commit instructions
- Prefer small commits with tests.
- Re-run both language test suites before commit or PR creation.
