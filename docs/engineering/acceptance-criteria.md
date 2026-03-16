# Acceptance criteria

Work in this repository is complete only when all of the following are true:

1. The Python example can load `LITELLM_API_KEY` and `LITELLM_BASE_URL` from the environment or `~/.env` and call `o3-deep-research` via REST.
2. The Java example can load the same configuration and call `o3-deep-research` via REST.
3. Each client has automated tests covering configuration loading, URL normalization, successful responses, and non-2xx errors.
4. Root documentation explains how to run both clients and how to avoid committing secrets.
5. Local verification includes:
   - `cd clients/python && uv run pytest`
   - `cd clients/java && mvn test`
6. If live credentials are available, at least one successful non-streaming call is observed for each language client before the work is declared complete.
