"""LiteLLM 예제 클라이언트의 HTTP 호출과 응답 해석을 담당한다."""

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
    "function": {
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
    },
}


class LiteLLMError(Exception):
    """LiteLLM 호출 중 발생한 HTTP 또는 네트워크 오류를 나타낸다."""

    def __init__(self, status: int, message: str, body: str | None = None) -> None:
        """상태 코드와 응답 본문을 포함한 예외 객체를 초기화한다."""
        super().__init__(message)
        self.status = status
        self.body = body


def _normalize_base_url(raw: str) -> str:
    """설정된 기본 URL을 일관된 ``/v1/`` API 루트로 정규화한다."""

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
    """채팅 대화의 단일 메시지를 표현한다."""

    role: str
    content: str


@dataclass
class ToolCallingResult:
    """Responses API tool calling 결과와 deep_research 메타데이터를 담는다."""

    final_text: str
    tool_called: bool
    response_id: str | None = None
    previous_response_id: str | None = None
    response_status: str | None = None
    tool_name: str | None = None
    tool_call_id: str | None = None
    invocation_id: str | None = None
    upstream_response_id: str | None = None
    research_summary: str | None = None


class LiteLLMClient:
    """LiteLLM OpenAI 호환 엔드포인트를 감싸는 작은 클라이언트다."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str = "o3-deep-research",
        timeout: float = 30.0,
    ) -> None:
        """기본 URL, 인증 정보, 모델, 타임아웃으로 클라이언트를 초기화한다."""
        self._base_url = _normalize_base_url(base_url)
        self._api_key = api_key
        self._model = model
        self._timeout = timeout

    def _chat_url(self) -> str:
        """채팅 완성 엔드포인트 URL을 반환한다."""
        return self._base_url.rstrip("/") + "/chat/completions"

    def _responses_url(self) -> str:
        """Responses API 엔드포인트 URL을 반환한다."""
        return self._base_url.rstrip("/") + "/responses"

    def _ssl_context(self) -> ssl.SSLContext:
        """certifi 번들을 사용하는 SSL 컨텍스트를 생성한다."""
        return ssl.create_default_context(cafile=certifi.where())

    def create_chat_completion(self, prompt: str) -> str:
        """최소한의 채팅 완성 요청을 보내고 첫 번째 답변 텍스트를 돌려준다."""

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
        """Responses API 요청을 보내고 사용 가능한 텍스트 결과를 반환한다."""

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

    def create_response_with_tool_calling(
        self,
        prompt: str,
        relay_base_url: str | None = None,
    ) -> ToolCallingResult:
        """Responses API 표준 function calling으로 deep_research를 실행한다."""
        payload: Dict[str, Any] = {
            "model": self._model,
            "input": prompt,
            "tools": [DEEP_RESEARCH_FUNCTION_TOOL],
        }
        first_response = self._post_json(self._responses_url(), payload)
        first_response_id = self._maybe_str(first_response.get("id"))
        first_status = self._maybe_str(first_response.get("status"))

        output = first_response.get("output") or []
        if not isinstance(output, list):
            raise LiteLLMError(
                200,
                "Response did not include any output items.",
                json.dumps(first_response),
            )

        deep_research_call = next(
            (
                item
                for item in output
                if isinstance(item, dict)
                and item.get("type") == "function_call"
                and item.get("name") == "deep_research"
            ),
            None,
        )

        if deep_research_call is None:
            return ToolCallingResult(
                final_text=self._extract_response_content(first_response),
                tool_called=False,
                response_id=first_response_id,
                response_status=first_status,
            )

        raw_args = str(deep_research_call.get("arguments", "{}"))
        try:
            tool_args = json.loads(raw_args)
        except json.JSONDecodeError:
            tool_args = {}

        research_question = tool_args.get("research_question", prompt)
        deliverable_format = tool_args.get("deliverable_format", "markdown_brief")
        tool_call_id = self._maybe_str(deep_research_call.get("call_id")) or "call_0"

        relay_url = (relay_base_url or "http://127.0.0.1:8080").rstrip("/")
        relay_tool_url = relay_url + "/api/v1/tool-invocations"
        relay_payload: Dict[str, Any] = {
            "tool_name": "deep_research",
            "arguments": {
                "research_question": research_question,
                "deliverable_format": deliverable_format,
                "background": False,
                "stream": False,
            },
        }
        relay_response = self._post_json(
            relay_tool_url, relay_payload, include_auth=False
        )
        research_summary = (
            relay_response.get("output_text")
            or (
                (relay_response.get("response") or {}).get("output_text")
                if isinstance(relay_response.get("response"), dict)
                else None
            )
            or ""
        )

        second_payload: Dict[str, Any] = {
            "model": self._model,
            "previous_response_id": first_response_id,
            "input": [
                {
                    "type": "function_call_output",
                    "call_id": tool_call_id,
                    "output": research_summary,
                }
            ],
        }
        second_response = self._post_json(self._responses_url(), second_payload)
        final_text = research_summary
        try:
            final_text = self._extract_response_content(second_response)
        except LiteLLMError:
            final_text = research_summary

        return ToolCallingResult(
            final_text=final_text,
            tool_called=True,
            response_id=self._maybe_str(second_response.get("id")),
            previous_response_id=first_response_id,
            response_status=self._maybe_str(second_response.get("status")),
            tool_name="deep_research",
            tool_call_id=tool_call_id,
            invocation_id=self._maybe_str(relay_response.get("invocation_id")),
            upstream_response_id=self._maybe_str(
                relay_response.get("upstream_response_id")
            ),
            research_summary=research_summary,
        )

    def create_chat_with_tool_calling(
        self,
        prompt: str,
        relay_base_url: str | None = None,
    ) -> tuple[str, bool]:
        """하위 호환을 위해 표준 Responses tool calling 결과를 튜플로 변환한다."""
        result = self.create_response_with_tool_calling(
            prompt, relay_base_url=relay_base_url
        )
        return result.final_text, result.tool_called

    def _post_json(
        self, url: str, payload: Dict[str, Any], include_auth: bool = True
    ) -> Dict[str, Any]:
        """JSON 본문을 POST하고 파싱된 응답 딕셔너리를 반환한다."""
        data = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if include_auth:
            headers["Authorization"] = f"Bearer {self._api_key}"
        req = request.Request(
            url,
            data=data,
            method="POST",
            headers=headers,
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
        """JSON 오류 본문에서 사람이 읽을 메시지를 추출한다."""
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
        """채팅 완성 응답에서 첫 번째 어시스턴트 텍스트를 추출한다."""
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
        """Responses API 결과 페이로드에서 텍스트를 추출한다."""
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

    @staticmethod
    def _maybe_str(value: Any) -> str | None:
        """비어 있지 않은 문자열만 반환하고 나머지는 ``None``으로 바꾼다."""
        return value if isinstance(value, str) and value else None
