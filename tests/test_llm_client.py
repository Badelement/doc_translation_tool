from __future__ import annotations

import json

import httpx
import pytest

from doc_translation_tool.config import LLMSettings
from doc_translation_tool.llm import (
    AnthropicCompatibleClient,
    LLMClientError,
    MockLLMClient,
    OpenAICompatibleClient,
    TranslationItem,
    create_llm_client,
)


def _build_settings() -> LLMSettings:
    return LLMSettings(
        provider="openai_compatible",
        api_format="openai",
        base_url="https://llm.example/v1",
        api_key="secret-key",
        model="test-model",
        timeout=60,
        connect_timeout=10,
        read_timeout=60,
        max_retries=2,
        batch_size=8,
        temperature=0.2,
    )


def test_create_llm_client_returns_openai_compatible_client() -> None:
    client = create_llm_client(_build_settings())
    assert isinstance(client, OpenAICompatibleClient)
    client.close()


def test_create_llm_client_returns_anthropic_compatible_client_for_api_format() -> None:
    client = create_llm_client(
        LLMSettings(
            provider="openai_compatible",
            api_format="anthropic",
            anthropic_version="2023-06-01",
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="test-model",
        )
    )
    assert isinstance(client, AnthropicCompatibleClient)
    client.close()


def test_create_llm_client_returns_mock_client() -> None:
    client = create_llm_client(
        LLMSettings(
            provider="mock",
            api_format="openai",
            base_url="",
            api_key="",
            model="mock-model",
        )
    )
    assert isinstance(client, MockLLMClient)
    client.close()


def test_openai_client_disables_proxy_env_lookup() -> None:
    client = OpenAICompatibleClient(_build_settings())

    assert client._client._trust_env is False
    client.close()


def test_openai_client_requires_core_settings() -> None:
    with pytest.raises(ValueError, match="base_url"):
        OpenAICompatibleClient(
            LLMSettings(
                provider="openai_compatible",
                api_format="openai",
                base_url="",
                api_key="secret-key",
                model="test-model",
            )
        )


def test_check_connection_posts_expected_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["auth"] = request.headers.get("Authorization")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": "OK",
                        }
                    }
                ]
            },
        )

    client = OpenAICompatibleClient(
        _build_settings(),
        transport=httpx.MockTransport(handler),
    )

    result = client.check_connection()

    assert result == "OK"
    assert captured["path"] == "/v1/chat/completions"
    assert captured["auth"] == "Bearer secret-key"
    assert captured["body"]["model"] == "test-model"
    client.close()


def test_translate_batch_returns_ordered_results() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "items": [
                                        {
                                            "id": "seg-001",
                                            "translated_text": "Translated one",
                                        },
                                        {
                                            "id": "seg-002",
                                            "translated_text": "Translated two",
                                        },
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = OpenAICompatibleClient(
        _build_settings(),
        transport=httpx.MockTransport(handler),
    )

    results = client.translate_batch(
        items=[
            TranslationItem(id="seg-001", text="原文一"),
            TranslationItem(id="seg-002", text="原文二"),
        ],
        direction="zh_to_en",
    )

    assert [item.id for item in results] == ["seg-001", "seg-002"]
    assert [item.translated_text for item in results] == [
        "Translated one",
        "Translated two",
    ]
    client.close()


def test_translate_batch_rejects_mismatched_ids() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                {
                                    "items": [
                                        {
                                            "id": "seg-999",
                                            "translated_text": "Wrong id",
                                        }
                                    ]
                                }
                            )
                        }
                    }
                ]
            },
        )

    client = OpenAICompatibleClient(
        _build_settings(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMClientError, match="IDs do not match"):
        client.translate_batch(
            items=[TranslationItem(id="seg-001", text="原文一")],
            direction="zh_to_en",
        )

    client.close()


def test_openai_client_formats_429_as_rate_limit_error() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            429,
            json={
                "error": {
                    "message": "rate limit exceeded",
                }
            },
        )

    client = OpenAICompatibleClient(
        _build_settings(),
        transport=httpx.MockTransport(handler),
    )

    with pytest.raises(LLMClientError, match="rate limited: HTTP 429"):
        client.check_connection()

    client.close()


def test_anthropic_client_posts_expected_request() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["path"] = request.url.path
        captured["api_key"] = request.headers.get("x-api-key")
        captured["anthropic_version"] = request.headers.get("anthropic-version")
        captured["body"] = json.loads(request.content.decode("utf-8"))
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": "OK",
                    }
                ]
            },
        )

    client = AnthropicCompatibleClient(
        LLMSettings(
            provider="openai_compatible",
            api_format="anthropic",
            anthropic_version="2023-06-01",
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="test-model",
        ),
        transport=httpx.MockTransport(handler),
    )

    result = client.check_connection()

    assert result == "OK"
    assert captured["path"] == "/v1/messages"
    assert captured["api_key"] == "secret-key"
    assert captured["anthropic_version"] == "2023-06-01"
    assert captured["body"]["model"] == "test-model"
    assert captured["body"]["max_tokens"] == 4096
    assert captured["body"]["messages"][0]["role"] == "user"
    client.close()


def test_anthropic_translate_batch_returns_ordered_results() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(
                            {
                                "items": [
                                    {
                                        "id": "seg-001",
                                        "translated_text": "Translated one",
                                    },
                                    {
                                        "id": "seg-002",
                                        "translated_text": "Translated two",
                                    },
                                ]
                            }
                        ),
                    }
                ]
            },
        )

    client = AnthropicCompatibleClient(
        LLMSettings(
            provider="openai_compatible",
            api_format="anthropic",
            anthropic_version="2023-06-01",
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="test-model",
        ),
        transport=httpx.MockTransport(handler),
    )

    results = client.translate_batch(
        items=[
            TranslationItem(id="seg-001", text="原文一"),
            TranslationItem(id="seg-002", text="原文二"),
        ],
        direction="zh_to_en",
    )

    assert [item.id for item in results] == ["seg-001", "seg-002"]
    assert [item.translated_text for item in results] == [
        "Translated one",
        "Translated two",
    ]
    client.close()


def test_mock_client_preserves_placeholders_and_returns_deterministic_text() -> None:
    client = MockLLMClient(
        LLMSettings(
            provider="mock",
            api_format="openai",
            base_url="",
            api_key="",
            model="mock-model",
        )
    )

    results = client.translate_batch(
        items=[
            TranslationItem(id="seg-001", text="这是 @@PROTECT_0@@ 测试"),
            TranslationItem(id="seg-002", text="This is a test"),
        ],
        direction="zh_to_en",
    )

    assert results[0].translated_text == "mock @@PROTECT_0@@ mock"
    assert results[1].translated_text.startswith("[MOCK EN] ")
    assert client.check_connection() == "Mock model ready"
    client.close()
