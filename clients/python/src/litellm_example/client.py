from __future__ import annotations

import json
import ssl
from dataclasses import dataclass
from typing import Any, Dict
from urllib import error, request
from urllib.parse import urlparse

import certifi


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

    def create_response(self, prompt: str, background: bool = False) -> str:
        """Send a minimal OpenAI-compatible responses API request.

        This uses ``POST /v1/responses`` with a small payload that LiteLLM can
        proxy for the configured model. The first usable text output is returned
        for foreground execution. When ``background=True`` is set, the raw JSON
        response is returned so callers can inspect identifiers and status.
        """

        payload = {
            "model": self._model,
            "input": prompt,
        }
        if background:
            payload["background"] = True

        parsed = self._post_json(self._responses_url(), payload)
        if background:
            return json.dumps(parsed, ensure_ascii=False)
        return self._extract_response_content(parsed)

    def _post_json(self, url: str, payload: Dict[str, Any]) -> Dict[str, Any]:
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
