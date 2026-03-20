from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any, Dict
from urllib import error, request
from urllib.parse import urlparse

import certifi

DEEP_RESEARCH_FUNCTION_TOOL: Dict[str, Any] = {
    "type": "function",
    "name": "deep_research",
    "description": (
        "Conduct in-depth research on a topic and return a detailed report. "
        "Use this when the user asks for detailed factual information, history, "
        "analysis, or comprehensive explanations that require research beyond "
        "general knowledge."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "research_question": {
                "type": "string",
                "description": "The specific research question or topic to investigate",
            },
            "deliverable_format": {
                "type": "string",
                "enum": ["markdown_brief", "markdown_report", "json_outline"],
                "description": "Format of the research output",
            },
        },
        "required": ["research_question", "deliverable_format"],
    },
}


class LiteLLMError(Exception):
    """Represents an error response or network failure when talking to LiteLLM."""

    def __init__(self, status: int, message: str, body: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.body = body


def _normalize_base_url(raw: str) -> str:
    """Normalise the configured base URL to a predictable /v1/ API root.

    Accepted forms:

    - https://host:4000
    - https://host:4000/
    - https://host:4000/v1
    - https://host:4000/v1/

    All of these are normalised to ``https://host:4000/v1/``. Other paths are
    rejected so that the example behaves predictably.
    """

    parsed = urlparse(raw)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError(
            "LITELLM_BASE_URL must include a scheme and host, for example "
            "https://localhost:4000 or https://localhost:4000/v1."
        )

    if parsed.scheme not in {"https", "http"}:
        raise ValueError("LITELLM_BASE_URL must use https or http.")

    if parsed.scheme == "http" and parsed.hostname not in {"localhost", "127.0.0.1"}:
        raise ValueError(
            "For security reasons this example only permits http URLs for "
            "localhost. Use https for remote LiteLLM endpoints."
        )

    path = parsed.path or ""
    if path in ("", "/"):
        path = "/v1/"
    elif path in ("/v1", "/v1/"):
        path = "/v1/"
    else:
        raise ValueError(
            "For this example, LITELLM_BASE_URL may only have an empty path or /v1."
        )

    return f"{parsed.scheme}://{parsed.netloc}{path}"


@dataclass
class ChatMessage:
    """A single message in a chat conversation."""

    role: str
    content: str


class LiteLLMClient:
    """Small wrapper around a LiteLLM chat completions endpoint."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "o3-deep-research",
        timeout: float = 30.0,
    ) -> None:
        self._base_url = _normalize_base_url(base_url)
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def _chat_url(self) -> str:
        return self._base_url.rstrip("/") + "/chat/completions"

    def _responses_url(self) -> str:
        return self._base_url.rstrip("/") + "/responses"

    def _ssl_context(self) -> ssl.SSLContext:
        return ssl.create_default_context(cafile=certifi.where())

    def create_chat_completion(self, prompt: str) -> str:
        """Send a minimal chat completion request and return the assistant text.

        This method uses the non-streaming OpenAI-compatible chat completions
        API and only extracts the first assistant message's content. It raises
        :class:`LiteLLMError` when the request fails, the response is invalid,
        or does not contain a usable assistant message.
        """

        payload = {
            "model": self._model,
            "messages": [
                {"role": "user", "content": prompt},
            ],
        }

        parsed = self._post_json(self._chat_url(), payload)
        return self._extract_content(parsed)

    def create_response(
        self,
        prompt: str,
        background: bool = False,
        tools: list[Dict[str, Any]] | None = None,
    ) -> str:
        """Send a minimal OpenAI-compatible responses API request.

        This uses ``POST /v1/responses`` with a small payload that LiteLLM can
        proxy for the configured model. The first usable text output is returned
        for foreground execution. When ``background=True`` is set, the raw JSON
        response is returned so callers can inspect identifiers and status.

        Pass ``tools=[{"type": "web_search_preview"}]`` to enable live web
        search on models that support it (e.g. ``gpt-4o``).  The LiteLLM Proxy
        must also have the ``web_search_preview`` tool enabled for the target
        model.
        """

        payload: Dict[str, Any] = {
            "model": self._model,
            "input": prompt,
        }
        if background:
            payload["background"] = True
        if tools:
            payload["tools"] = tools

        parsed = self._post_json(self._responses_url(), payload)
        if background:
            return json.dumps(parsed, ensure_ascii=False)
        return self._extract_response_content(parsed)

    def create_chat_with_tool_calling(
        self,
        prompt: str,
        relay_base_url: str | None = None,
    ) -> tuple[str, bool]:
        """Send a Responses API request with the deep_research function tool.

        Returns ``(answer_text, tool_was_called)``.

        When the model decides to call deep_research, this method:

        1. Sends the first Responses API turn with the ``deep_research``
           function tool attached.
        2. If the model returns a ``function_call`` output item for
           ``deep_research``, calls the relay ``POST /api/v1/tool-invocations``
           endpoint to execute the research.
        3. Sends a second Responses API turn using ``previous_response_id`` and
           a ``function_call_output`` item so the model can synthesise a final
           natural-language answer.
        4. Returns ``(final_answer, True)``.

        When the model answers directly (no tool call), returns
        ``(answer, False)``.

        Parameters
        ----------
        prompt:
            The user message.
        relay_base_url:
            Base URL of the relay server (e.g. ``http://127.0.0.1:8080``).
            Defaults to ``http://127.0.0.1:8080`` when not provided.
        """
        # First turn: Responses API with tool schema
        payload: Dict[str, Any] = {
            "model": self._model,
            "input": prompt,
            "tools": [DEEP_RESEARCH_FUNCTION_TOOL],
        }
        first_response = self._post_json(self._responses_url(), payload)

        deep_research_call = self._extract_function_call(first_response)
        if deep_research_call is None:
            return self._extract_response_content(first_response), False

        raw_args = deep_research_call.get("arguments", "{}")
        try:
            tool_args = json.loads(raw_args)
        except json.JSONDecodeError:
            tool_args = {}

        research_question = tool_args.get("research_question", prompt)
        deliverable_format = tool_args.get("deliverable_format", "markdown_brief")
        call_id = str(deep_research_call.get("call_id") or "call_0")

        # Call relay /api/v1/tool-invocations to execute the deep research
        relay_url = (relay_base_url or "http://127.0.0.1:8080").rstrip("/")
        relay_tool_url = relay_url + "/api/v1/tool-invocations"
        relay_payload: Dict[str, Any] = {
            "tool_name": "deep_research",
            "arguments": {
                "research_question": research_question,
                "deliverable_format": deliverable_format,
            },
        }
        relay_response = self._post_json(relay_tool_url, relay_payload)
        research_summary = (
            relay_response.get("output_text")
            or relay_response.get("research_summary")
            or relay_response.get("content")
            or ""
        )

        response_id = self._extract_response_id(first_response)
        second_payload: Dict[str, Any] = {
            "model": self._model,
            "previous_response_id": response_id,
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": call_id,
                    "output": research_summary,
                }
            ],
        }
        second_response = self._post_json(self._responses_url(), second_payload)
        try:
            final_content = self._extract_response_content(second_response)
        except LiteLLMError:
            return research_summary, True
        return final_content, True

    @staticmethod
    def _extract_function_call(payload: Dict[str, Any]) -> Dict[str, Any] | None:
        output = payload.get("output") or []
        if not isinstance(output, list):
            raise LiteLLMError(
                200,
                "Response did not include a usable output array.",
                json.dumps(payload),
            )

        for item in output:
            if not isinstance(item, dict):
                continue
            if item.get("type") != "function_call":
                continue
            if item.get("name") != "deep_research":
                continue
            return item
        return None

    @staticmethod
    def _extract_response_id(payload: Dict[str, Any]) -> str:
        response_id = payload.get("id")
        if isinstance(response_id, str) and response_id.strip():
            return response_id
        raise LiteLLMError(
            200, "Response did not include a usable id.", json.dumps(payload)
        )

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """POST *payload* as JSON to *url* and return the parsed response dict."""
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url,
            data=data,
            method="POST",
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )

        try:
            with request.urlopen(
                req,
                timeout=self._timeout,
                context=self._ssl_context(),
            ) as resp:  # type: ignore[call-arg]
                status = getattr(resp, "status", resp.getcode())
                body_bytes = resp.read()
        except error.HTTPError as exc:  # non-2xx
            body_bytes = exc.read()
            text = body_bytes.decode("utf-8", errors="replace")
            message = self._extract_error_message(text)
            raise LiteLLMError(exc.code, message, text) from None
        except OSError as exc:
            raise LiteLLMError(
                -1, f"Network error while calling LiteLLM: {exc}", None
            ) from exc

        text = body_bytes.decode("utf-8", errors="replace")
        if status < 200 or status >= 300:
            message = self._extract_error_message(text)
            raise LiteLLMError(status, message, text)

        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            raise LiteLLMError(status, "LiteLLM responded with invalid JSON.", text)

        if not isinstance(parsed, dict):
            raise LiteLLMError(
                status, "LiteLLM responded with an unexpected JSON shape.", text
            )

        return parsed

    @staticmethod
    def _extract_error_message(text: str) -> str:
        """Try to extract a human-readable error message from a JSON error body."""
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            return "LiteLLM returned an error response."

        err = data.get("error")
        if isinstance(err, dict):
            for key in ("message", "error", "detail"):
                value = err.get(key)
                if isinstance(value, str) and value.strip():
                    return value
        return "LiteLLM returned an error response."

    @staticmethod
    def _extract_content(payload: Dict[str, Any]) -> str:
        """Extract the first assistant message text from a chat completions response."""
        choices = payload.get("choices") or []
        if not isinstance(choices, list) or not choices:
            raise LiteLLMError(
                200, "Response did not include any choices.", json.dumps(payload)
            )

        first = choices[0]
        if not isinstance(first, dict):
            raise LiteLLMError(
                200, "Unexpected choice format in response.", json.dumps(payload)
            )

        message = first.get("message") or {}
        if not isinstance(message, dict):
            raise LiteLLMError(
                200, "Response did not include a message object.", json.dumps(payload)
            )

        content = message.get("content")
        if isinstance(content, str) and content.strip():
            return content

        # Be tolerant of a future list-of-blocks representation but keep the
        # example simple: look for "text" fields and join them.
        if isinstance(content, list):
            parts: list[str] = []
            for block in content:
                if isinstance(block, dict):
                    text = block.get("text")
                    if isinstance(text, str):
                        parts.append(text)
            if parts:
                return "".join(parts)

        raise LiteLLMError(
            200,
            "Response did not include a usable assistant message.",
            json.dumps(payload),
        )

    @staticmethod
    def _extract_response_content(payload: Dict[str, Any]) -> str:
        """Extract text from a LiteLLM responses API result payload."""
        output_text = payload.get("output_text")
        if isinstance(output_text, str) and output_text.strip():
            return output_text

        output = payload.get("output") or []
        if not isinstance(output, list) or not output:
            raise LiteLLMError(
                200, "Response did not include any output items.", json.dumps(payload)
            )

        parts: list[str] = []
        for item in output:
            if not isinstance(item, dict):
                continue
            content = item.get("content") or []
            if not isinstance(content, list):
                continue
            for block in content:
                if not isinstance(block, dict):
                    continue
                if block.get("type") not in {"output_text", "text"}:
                    continue
                text = block.get("text")
                if isinstance(text, str) and text:
                    parts.append(text)
                elif isinstance(text, dict):
                    value = text.get("value")
                    if isinstance(value, str) and value:
                        parts.append(value)

        if parts:
            return "".join(parts)

        raise LiteLLMError(
            200,
            "Response did not include a usable text output.",
            json.dumps(payload),
        )
