from __future__ import annotations

import json
import re
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

import httpx

from doc_translation_tool.config import LLMSettings
from doc_translation_tool.llm.prompt import (
    build_connectivity_system_prompt,
    build_connectivity_user_prompt,
    build_translation_system_prompt,
    build_translation_user_prompt,
)


@dataclass(slots=True)
class TranslationItem:
    """Single translation input item sent to the model."""

    id: str
    text: str


@dataclass(slots=True)
class TranslationResult:
    """Single translation output item returned by the model."""

    id: str
    translated_text: str


class LLMClientError(RuntimeError):
    """Base error for model client failures."""


class BaseLLMClient(ABC):
    """Abstract interface for all model clients."""

    def __init__(self, settings: LLMSettings) -> None:
        self.settings = settings

    @abstractmethod
    def check_connection(self) -> str:
        """Verify that the model endpoint is reachable and usable."""

    @abstractmethod
    def translate_batch(
        self,
        items: list[TranslationItem],
        direction: str,
        glossary: list[dict[str, str]] | None = None,
    ) -> list[TranslationResult]:
        """Translate a batch of protected text segments."""

    @abstractmethod
    def close(self) -> None:
        """Release client resources."""


class _HTTPJSONLLMClient(BaseLLMClient):
    """Shared HTTP/JSON helpers for compatible model endpoints."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        headers: dict[str, str],
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(settings)
        self._client: httpx.Client | None = None
        self._validate_settings()
        self._client = self._build_http_client(headers=headers, transport=transport)

    def close(self) -> None:
        if self._client is not None:
            self._client.close()

    def _validate_settings(self) -> None:
        if not self.settings.base_url.strip():
            raise ValueError("LLM base_url is required.")
        if not self.settings.api_key.strip():
            raise ValueError("LLM api_key is required.")
        if not self.settings.model.strip():
            raise ValueError("LLM model is required.")

    def _build_http_client(
        self,
        *,
        headers: dict[str, str],
        transport: httpx.BaseTransport | None,
    ) -> httpx.Client:
        return httpx.Client(
            base_url=self.settings.base_url.rstrip("/"),
            headers=headers,
            timeout=httpx.Timeout(
                self.settings.timeout,
                connect=self.settings.connect_timeout,
                read=self.settings.read_timeout,
            ),
            transport=transport,
            trust_env=False,
        )

    def _post_json(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post(path, json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(self._format_http_status_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"Model request failed: {exc}") from exc

        return self._parse_response_json(response)

    def _parse_response_json(self, response: httpx.Response) -> dict[str, Any]:
        data = response.json()
        if not isinstance(data, dict):
            raise LLMClientError("Model response must be a JSON object.")
        return data

    def _format_http_status_error(self, exc: httpx.HTTPStatusError) -> str:
        response = exc.response
        status_code = response.status_code
        reason = response.reason_phrase or "HTTP error"
        detail = self._extract_error_detail(response)

        if status_code == 429:
            message = (
                f"Model request rate limited: HTTP {status_code} {reason}. "
                "The endpoint is throttling requests or rejecting current concurrency."
            )
        else:
            message = f"Model request failed: HTTP {status_code} {reason}."

        if detail:
            message = f"{message} Detail: {detail}"
        return message

    def _extract_error_detail(self, response: httpx.Response) -> str:
        try:
            payload = response.json()
        except ValueError:
            return response.text.strip()

        if isinstance(payload, dict):
            error = payload.get("error")
            if isinstance(error, dict):
                message = error.get("message")
                if isinstance(message, str):
                    return message.strip()

            message = payload.get("message")
            if isinstance(message, str):
                return message.strip()

        return ""

    def _extract_text_content(
        self,
        content: Any,
        *,
        invalid_format_error: str,
        empty_content_error: str | None = None,
    ) -> str:
        if isinstance(content, str):
            text = content.strip()
        elif isinstance(content, list):
            text = self._join_text_parts(content)
        else:
            raise LLMClientError(invalid_format_error)

        if empty_content_error is not None and not text:
            raise LLMClientError(empty_content_error)
        return text

    def _join_text_parts(self, content_parts: list[Any]) -> str:
        text_parts: list[str] = []
        for part in content_parts:
            if not isinstance(part, dict) or part.get("type") != "text":
                continue
            text = part.get("text", "")
            if isinstance(text, str):
                text_parts.append(text)
        return "".join(text_parts).strip()

    def _parse_required_json_content(self, content: str) -> dict[str, Any]:
        parsed_content = self._parse_json_content(content)
        if not isinstance(parsed_content, dict):
            raise LLMClientError("Parsed model content must be a JSON object.")
        return parsed_content

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = self._strip_markdown_code_fence(cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMClientError("Model did not return valid JSON content.") from exc
        return parsed

    def _build_translation_results(
        self,
        *,
        request_items: list[TranslationItem],
        parsed_content: dict[str, Any],
    ) -> list[TranslationResult]:
        raw_items = parsed_content.get("items")
        if not isinstance(raw_items, list):
            raise LLMClientError("Translated response must contain an 'items' list.")

        expected_ids = [item.id for item in request_items]
        results: list[TranslationResult] = []

        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                raise LLMClientError("Each translated item must be a JSON object.")
            item_id = raw_item.get("id")
            translated_text = raw_item.get("translated_text")
            if not isinstance(item_id, str) or not isinstance(translated_text, str):
                raise LLMClientError("Translated items must contain string 'id' and 'translated_text'.")
            results.append(
                TranslationResult(
                    id=item_id,
                    translated_text=translated_text,
                )
            )

        result_ids = [item.id for item in results]
        if result_ids != expected_ids:
            raise LLMClientError("Translated item IDs do not match the request order.")

        return results

    def _strip_markdown_code_fence(self, content: str) -> str:
        lines = content.splitlines()
        if len(lines) >= 3 and lines[0].startswith("```") and lines[-1].startswith("```"):
            return "\n".join(lines[1:-1]).strip()
        return content


class OpenAICompatibleClient(_HTTPJSONLLMClient):
    """HTTP client for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            settings,
            headers={
                "Authorization": f"Bearer {settings.api_key}",
                "Content-Type": "application/json",
            },
            transport=transport,
        )

    def check_connection(self) -> str:
        response_json = self._post_json(
            "/chat/completions",
            self._build_connectivity_payload(),
        )
        return self._extract_openai_message_content(response_json)

    def translate_batch(
        self,
        items: list[TranslationItem],
        direction: str,
        glossary: list[dict[str, str]] | None = None,
    ) -> list[TranslationResult]:
        if not items:
            return []

        response_json = self._post_json(
            "/chat/completions",
            self._build_translation_payload(
                items=items,
                direction=direction,
                glossary=glossary,
            ),
        )
        parsed_content = self._parse_required_json_content(
            self._extract_openai_message_content(
                response_json,
                empty_content_error=None,
            )
        )
        return self._build_translation_results(
            request_items=items,
            parsed_content=parsed_content,
        )

    def _build_connectivity_payload(self) -> dict[str, Any]:
        payload = {
            "model": self.settings.model,
            "temperature": 0,
            "messages": [
                {
                    "role": "system",
                    "content": build_connectivity_system_prompt(),
                },
                {
                    "role": "user",
                    "content": build_connectivity_user_prompt(),
                },
            ],
        }
        if self.settings.max_tokens is not None:
            payload["max_tokens"] = self.settings.max_tokens
        return payload

    def _build_translation_payload(
        self,
        *,
        items: list[TranslationItem],
        direction: str,
        glossary: list[dict[str, str]] | None,
    ) -> dict[str, Any]:
        payload = {
            "model": self.settings.model,
            "temperature": self.settings.temperature,
            "messages": [
                {
                    "role": "system",
                    "content": build_translation_system_prompt(),
                },
                {
                    "role": "user",
                    "content": build_translation_user_prompt(
                        items=items,
                        direction=direction,
                        glossary=glossary,
                    ),
                },
            ],
        }
        if self.settings.max_tokens is not None:
            payload["max_tokens"] = self.settings.max_tokens
        return payload

    def _extract_openai_message_content(
        self,
        response_json: dict[str, Any],
        *,
        empty_content_error: str | None = "Model connectivity check returned empty content.",
    ) -> str:
        try:
            message = response_json["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError(
                "Model response does not contain a valid message."
            ) from exc

        return self._extract_text_content(
            message.get("content", ""),
            invalid_format_error="Unsupported message content format returned by model.",
            empty_content_error=empty_content_error,
        )


class AnthropicCompatibleClient(_HTTPJSONLLMClient):
    """HTTP client for Anthropic-compatible messages endpoints."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(
            settings,
            headers={
                "x-api-key": settings.api_key,
                "anthropic-version": settings.anthropic_version,
                "Content-Type": "application/json",
            },
            transport=transport,
        )

    def check_connection(self) -> str:
        response_json = self._post_json("/messages", self._build_connectivity_payload())
        return self._extract_anthropic_message_content(
            response_json,
            empty_content_error="Model connectivity check returned empty content.",
        )

    def translate_batch(
        self,
        items: list[TranslationItem],
        direction: str,
        glossary: list[dict[str, str]] | None = None,
    ) -> list[TranslationResult]:
        if not items:
            return []

        response_json = self._post_json(
            "/messages",
            self._build_translation_payload(
                items=items,
                direction=direction,
                glossary=glossary,
            ),
        )
        parsed_content = self._parse_required_json_content(
            self._extract_anthropic_message_content(response_json)
        )
        return self._build_translation_results(
            request_items=items,
            parsed_content=parsed_content,
        )

    def _build_connectivity_payload(self) -> dict[str, Any]:
        return {
            "model": self.settings.model,
            "system": build_connectivity_system_prompt(),
            "messages": [
                {
                    "role": "user",
                    "content": build_connectivity_user_prompt(),
                }
            ],
            "temperature": 0,
            "max_tokens": self._resolve_max_tokens(),
        }

    def _build_translation_payload(
        self,
        *,
        items: list[TranslationItem],
        direction: str,
        glossary: list[dict[str, str]] | None,
    ) -> dict[str, Any]:
        return {
            "model": self.settings.model,
            "system": build_translation_system_prompt(),
            "messages": [
                {
                    "role": "user",
                    "content": build_translation_user_prompt(
                        items=items,
                        direction=direction,
                        glossary=glossary,
                    ),
                }
            ],
            "temperature": self.settings.temperature,
            "max_tokens": self._resolve_max_tokens(),
        }

    def _resolve_max_tokens(self) -> int:
        if self.settings.max_tokens is not None:
            return self.settings.max_tokens
        return 4096

    def _extract_anthropic_message_content(
        self,
        response_json: dict[str, Any],
        *,
        empty_content_error: str | None = "Model response does not contain text content.",
    ) -> str:
        return self._extract_text_content(
            response_json.get("content"),
            invalid_format_error="Model response does not contain valid Anthropic content.",
            empty_content_error=empty_content_error,
        )


class MockLLMClient(BaseLLMClient):
    """Deterministic offline client used to verify the full app flow without real API calls."""

    _PLACEHOLDER_RE = re.compile(r"(@@PROTECT_\d+@@)")
    _PLACEHOLDER_FULL_RE = re.compile(r"@@PROTECT_\d+@@")
    _ZH_RUN_RE = re.compile(r"[\u4e00-\u9fff]+")
    _EN_RUN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_\-]*")

    def check_connection(self) -> str:
        return "Mock model ready"

    def translate_batch(
        self,
        items: list[TranslationItem],
        direction: str,
        glossary: list[dict[str, str]] | None = None,
    ) -> list[TranslationResult]:
        return [
            TranslationResult(
                id=item.id,
                translated_text=self._mock_translate_text(item.text, direction),
            )
            for item in items
        ]

    def close(self) -> None:
        return None

    def _mock_translate_text(self, text: str, direction: str) -> str:
        parts = self._PLACEHOLDER_RE.split(text)
        translated_parts: list[str] = []
        for part in parts:
            if self._PLACEHOLDER_FULL_RE.fullmatch(part):
                translated_parts.append(part)
                continue
            translated_parts.append(self._mock_translate_fragment(part, direction))
        return "".join(translated_parts)

    def _mock_translate_fragment(self, text: str, direction: str) -> str:
        if not text.strip():
            return text

        if direction == "zh_to_en":
            translated = self._ZH_RUN_RE.sub("mock", text)
            if translated == text:
                return f"[MOCK EN] {text}"
            return translated

        translated = self._EN_RUN_RE.sub("mock", text)
        if translated == text:
            return f"[MOCK ZH] {text}"
        return translated


def create_llm_client(
    settings: LLMSettings,
    *,
    transport: httpx.BaseTransport | None = None,
) -> BaseLLMClient:
    if settings.provider == "openai_compatible":
        if settings.api_format == "openai":
            return OpenAICompatibleClient(settings, transport=transport)
        if settings.api_format == "anthropic":
            return AnthropicCompatibleClient(settings, transport=transport)
        raise ValueError(f"Unsupported LLM api_format: {settings.api_format}")
    if settings.provider == "anthropic_compatible":
        return AnthropicCompatibleClient(settings, transport=transport)
    if settings.provider == "compatible":
        if settings.api_format == "openai":
            return OpenAICompatibleClient(settings, transport=transport)
        if settings.api_format == "anthropic":
            return AnthropicCompatibleClient(settings, transport=transport)
        raise ValueError(f"Unsupported LLM api_format: {settings.api_format}")
    if settings.provider == "mock":
        return MockLLMClient(settings)

    raise ValueError(f"Unsupported LLM provider: {settings.provider}")
