from __future__ import annotations

import json
from typing import Protocol


class TranslationItemLike(Protocol):
    id: str
    text: str


def build_connectivity_system_prompt() -> str:
    return "You are a connectivity check. Reply with OK only."


def build_connectivity_user_prompt() -> str:
    return "Reply with OK."


def build_translation_system_prompt() -> str:
    return (
        "You translate technical documentation segments. "
        "Return JSON only. Do not add explanations or markdown fences. "
        "Preserve the input item IDs exactly. "
        "Do not change protected placeholders such as @@PROTECT_0001@@. "
        "Keep every protected placeholder exactly once and in the same order as the source. "
        "Translate all natural language surrounding placeholders completely. "
        "If a placeholder appears inside a sentence, keep the placeholder unchanged "
        "but translate the text before and after it into the target language. "
        "Do not leave source-language text outside protected placeholders. "
        "Use the requested target language consistently for every sentence outside protected placeholders. "
        "Do not partially translate a sentence. "
        "If the direction is zh_to_en, write natural English outside protected placeholders. "
        "If the direction is en_to_zh, write Simplified Chinese outside protected placeholders. "
        "Keep product names, system names, and glossary terms stable when appropriate. "
        "Return an object with one field named 'items'. "
        "Each item must include 'id' and 'translated_text'."
    )


def build_translation_user_prompt(
    *,
    items: list[TranslationItemLike],
    direction: str,
    glossary: list[dict[str, str]] | None = None,
) -> str:
    source_language, target_language = _resolve_direction_languages(direction)
    payload = {
        "direction": direction,
        "source_language": source_language,
        "target_language": target_language,
        "quality_requirements": [
            "Translate every item fully into the target language.",
            "Do not leave source-language fragments outside protected placeholders.",
            "Keep protected placeholders unchanged and in the same order.",
            "Apply glossary entries when they match the source text.",
        ],
        "items": [
            {
                "id": item.id,
                "text": item.text,
            }
            for item in items
        ],
        "glossary": glossary or [],
    }
    return json.dumps(payload, ensure_ascii=False)


def _resolve_direction_languages(direction: str) -> tuple[str, str]:
    if direction == "zh_to_en":
        return ("Chinese", "English")
    if direction == "en_to_zh":
        return ("English", "Simplified Chinese")
    raise ValueError(f"Unsupported translation direction: {direction}")
