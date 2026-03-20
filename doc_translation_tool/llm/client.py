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


class OpenAICompatibleClient(BaseLLMClient):
    """HTTP client for OpenAI-compatible chat completion endpoints."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        super().__init__(settings)
        self._validate_settings()
        self._client = httpx.Client(
            base_url=self.settings.base_url.rstrip("/"),
            headers={
                "Authorization": f"Bearer {self.settings.api_key}",
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(
                self.settings.timeout,
                connect=self.settings.connect_timeout,
                read=self.settings.read_timeout,
            ),
            transport=transport,
            trust_env=False,
        )

    def check_connection(self) -> str:
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

        response_json = self._post_chat_completion(payload)
        content = self._extract_message_content(response_json)
        if not content:
            raise LLMClientError("Model connectivity check returned empty content.")
        return content

    def translate_batch(
        self,
        items: list[TranslationItem],
        direction: str,
        glossary: list[dict[str, str]] | None = None,
    ) -> list[TranslationResult]:
        if not items:
            return []

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

        response_json = self._post_chat_completion(payload)
        content = self._extract_message_content(response_json)
        parsed_content = self._parse_json_content(content)
        return self._build_translation_results(
            request_items=items,
            parsed_content=parsed_content,
        )

    def close(self) -> None:
        self._client.close()

    def _validate_settings(self) -> None:
        if not self.settings.base_url.strip():
            raise ValueError("LLM base_url is required.")
        if not self.settings.api_key.strip():
            raise ValueError("LLM api_key is required.")
        if not self.settings.model.strip():
            raise ValueError("LLM model is required.")

    def _post_chat_completion(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post("/chat/completions", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(self._format_http_status_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"Model request failed: {exc}") from exc

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

    def _extract_message_content(self, response_json: dict[str, Any]) -> str:
        try:
            message = response_json["choices"][0]["message"]
        except (KeyError, IndexError, TypeError) as exc:
            raise LLMClientError("Model response does not contain a valid message.") from exc

        content = message.get("content", "")
        if isinstance(content, str):
            return content.strip()

        if isinstance(content, list):
            text_parts: list[str] = []
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text":
                    text = part.get("text", "")
                    if isinstance(text, str):
                        text_parts.append(text)
            return "".join(text_parts).strip()

        raise LLMClientError("Unsupported message content format returned by model.")

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        cleaned = content.strip()
        if cleaned.startswith("```"):
            cleaned = self._strip_markdown_code_fence(cleaned)

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise LLMClientError("Model did not return valid JSON content.") from exc

        if not isinstance(parsed, dict):
            raise LLMClientError("Parsed model content must be a JSON object.")
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


class AnthropicCompatibleClient(OpenAICompatibleClient):
    """HTTP client for Anthropic-compatible messages endpoints."""

    def __init__(
        self,
        settings: LLMSettings,
        *,
        transport: httpx.BaseTransport | None = None,
    ) -> None:
        BaseLLMClient.__init__(self, settings)
        self._validate_settings()
        self._client = httpx.Client(
            base_url=self.settings.base_url.rstrip("/"),
            headers={
                "x-api-key": self.settings.api_key,
                "anthropic-version": self.settings.anthropic_version,
                "Content-Type": "application/json",
            },
            timeout=httpx.Timeout(
                self.settings.timeout,
                connect=self.settings.connect_timeout,
                read=self.settings.read_timeout,
            ),
            transport=transport,
            trust_env=False,
        )

    def check_connection(self) -> str:
        payload = {
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

        response_json = self._post_messages(payload)
        content = self._extract_anthropic_message_content(response_json)
        if not content:
            raise LLMClientError("Model connectivity check returned empty content.")
        return content

    def translate_batch(
        self,
        items: list[TranslationItem],
        direction: str,
        glossary: list[dict[str, str]] | None = None,
    ) -> list[TranslationResult]:
        if not items:
            return []

        payload = {
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

        response_json = self._post_messages(payload)
        content = self._extract_anthropic_message_content(response_json)
        parsed_content = self._parse_json_content(content)
        return self._build_translation_results(
            request_items=items,
            parsed_content=parsed_content,
        )

    def _resolve_max_tokens(self) -> int:
        if self.settings.max_tokens is not None:
            return self.settings.max_tokens
        return 4096

    def _post_messages(self, payload: dict[str, Any]) -> dict[str, Any]:
        try:
            response = self._client.post("/messages", json=payload)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise LLMClientError(self._format_http_status_error(exc)) from exc
        except httpx.HTTPError as exc:
            raise LLMClientError(f"Model request failed: {exc}") from exc

        data = response.json()
        if not isinstance(data, dict):
            raise LLMClientError("Model response must be a JSON object.")
        return data

    def _extract_anthropic_message_content(self, response_json: dict[str, Any]) -> str:
        content = response_json.get("content")
        if isinstance(content, str):
            return content.strip()

        if not isinstance(content, list):
            raise LLMClientError("Model response does not contain valid Anthropic content.")

        text_parts: list[str] = []
        for part in content:
            if not isinstance(part, dict):
                continue
            if part.get("type") != "text":
                continue
            text = part.get("text", "")
            if isinstance(text, str):
                text_parts.append(text)

        combined = "".join(text_parts).strip()
        if not combined:
            raise LLMClientError("Model response does not contain text content.")
        return combined


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
