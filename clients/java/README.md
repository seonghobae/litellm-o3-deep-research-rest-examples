## Java client

This directory contains a small Java 21 client that calls a LiteLLM-compatible
REST API using the OpenAI chat completions format to reach the
`o3-deep-research` model.

Configuration is read from environment variables, with an optional
`~/.env` file fallback.

### Quickstart

```bash
cd clients/java
mvn test
```

Run the example CLI (requires valid environment variables):

```bash
cd clients/java
mvn -q exec:java -Dexec.mainClass=example.litellm.Main -Dexec.args="Explain what o3-deep-research is useful for"
```
