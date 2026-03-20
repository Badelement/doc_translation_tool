"""LLM integration package."""

from doc_translation_tool.llm.client import (
    AnthropicCompatibleClient,
    BaseLLMClient,
    LLMClientError,
    MockLLMClient,
    OpenAICompatibleClient,
    TranslationItem,
    TranslationResult,
    create_llm_client,
)
from doc_translation_tool.llm.prompt import (
    build_connectivity_system_prompt,
    build_connectivity_user_prompt,
    build_translation_system_prompt,
    build_translation_user_prompt,
)

__all__ = [
    "BaseLLMClient",
    "LLMClientError",
    "MockLLMClient",
    "AnthropicCompatibleClient",
    "OpenAICompatibleClient",
    "TranslationItem",
    "TranslationResult",
    "build_connectivity_system_prompt",
    "build_connectivity_user_prompt",
    "build_translation_system_prompt",
    "build_translation_user_prompt",
    "create_llm_client",
]
