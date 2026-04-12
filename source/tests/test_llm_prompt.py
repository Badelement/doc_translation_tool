import json

from doc_translation_tool.llm import (
    TranslationItem,
    build_connectivity_system_prompt,
    build_connectivity_user_prompt,
    build_translation_system_prompt,
    build_translation_user_prompt,
)


def test_connectivity_prompts_are_stable() -> None:
    assert build_connectivity_system_prompt() == "You are a connectivity check. Reply with OK only."
    assert build_connectivity_user_prompt() == "Reply with OK."


def test_translation_system_prompt_mentions_json_and_placeholders() -> None:
    prompt = build_translation_system_prompt()

    assert "Return JSON only" in prompt
    assert "translated_text" in prompt
    assert "@@PROTECT_" in prompt
    assert "technical documentation segments" in prompt
    assert "surrounding placeholders" in prompt
    assert "Do not leave source-language text outside protected placeholders" in prompt
    assert "same order as the source" in prompt
    assert "Do not partially translate a sentence" in prompt
    assert "Simplified Chinese" in prompt


def test_translation_user_prompt_serializes_direction_items_and_glossary() -> None:
    payload = json.loads(
        build_translation_user_prompt(
            items=[
                TranslationItem(id="seg-001", text="原文一"),
                TranslationItem(id="seg-002", text="Original text two"),
            ],
            direction="zh_to_en",
            glossary=[
                {
                    "source": "远程处理音效",
                    "target": "remote sound effect",
                }
            ],
        )
    )

    assert payload["direction"] == "zh_to_en"
    assert payload["source_language"] == "Chinese"
    assert payload["target_language"] == "English"
    assert payload["items"][0]["id"] == "seg-001"
    assert payload["items"][1]["text"] == "Original text two"
    assert payload["glossary"][0]["target"] == "remote sound effect"
    assert "Do not leave source-language fragments outside protected placeholders." in payload[
        "quality_requirements"
    ]


def test_translation_user_prompt_serializes_en_to_zh_target_language() -> None:
    payload = json.loads(
        build_translation_user_prompt(
            items=[TranslationItem(id="seg-003", text="Original text three")],
            direction="en_to_zh",
        )
    )

    assert payload["source_language"] == "English"
    assert payload["target_language"] == "Simplified Chinese"
