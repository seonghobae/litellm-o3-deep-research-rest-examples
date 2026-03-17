# Acceptance criteria

Work in this repository is complete only when all of the following are true:

1. The Python example can load `LITELLM_API_KEY` and `LITELLM_BASE_URL` from the environment or `~/.env` and call `o3-deep-research` via both `chat/completions` and `responses` REST APIs.
2. The Java example can load the same configuration and call `o3-deep-research` via both APIs.
3. Each client supports `responses` requests with `background: true` and returns raw response metadata when background mode is used.
4. Each client has automated tests covering configuration loading, URL normalization, successful `chat/completions` and `responses` calls, background `responses` request handling, and non-2xx errors.
5. Root documentation explains how to run both clients, how background responses differ from foreground CLI execution, and how to avoid committing secrets.
6. Local verification includes:
   - `cd clients/python && uv run pytest`
   - `cd clients/java && mvn test`
7. If live credentials are available, at least one successful non-streaming foreground call is observed for each supported API style in each language, and at least one successful `background: true` response submission is observed in each language before the work is declared complete.
