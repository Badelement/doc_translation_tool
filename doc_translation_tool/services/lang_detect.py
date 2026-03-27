from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from doc_translation_tool.documents import get_handler_for_document_type
from doc_translation_tool.document_types import detect_document_type


_CODE_BLOCK_RE = re.compile(r"```.*?```", re.S)
_INLINE_CODE_RE = re.compile(r"`[^`\n]+`")
_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
_LINK_RE = re.compile(r"\[([^\]]*)\]\(([^)]*)\)")
_URL_RE = re.compile(r"https?://\S+")
_PATHISH_RE = re.compile(r"(?<!\w)(?:[A-Za-z]:\\|\.?/)[^\s]+")
_SPECIAL_MARK_RE = re.compile(r"^:::(note|tip|warning)\s*$", re.M | re.I)
_XML_TAG_RE = re.compile(r"</?[A-Za-z_][A-Za-z0-9._:-]*(?:\s+[^<>\n]*?)?\s*/?>")
_ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
_EN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z'-]{1,}\b")


@dataclass(slots=True)
class LanguageDetectionResult:
    """Heuristic language detection result for supported documents."""

    language: str
    zh_char_count: int
    en_word_count: int
    sample_length: int

    @property
    def is_confident(self) -> bool:
        return self.language in {"zh", "en"}


def detect_language_from_text(text: str) -> LanguageDetectionResult:
    cleaned = _sanitize_text(text)
    zh_count = len(_ZH_CHAR_RE.findall(cleaned))
    en_count = len(_EN_WORD_RE.findall(cleaned))

    if zh_count == 0 and en_count == 0:
        language = "mixed_or_unknown"
    elif zh_count >= max(6, en_count * 2):
        language = "zh"
    elif en_count >= max(6, zh_count * 2):
        language = "en"
    else:
        language = "mixed_or_unknown"

    return LanguageDetectionResult(
        language=language,
        zh_char_count=zh_count,
        en_word_count=en_count,
        sample_length=len(cleaned),
    )


def detect_language_from_file(path: str | Path) -> LanguageDetectionResult:
    text = Path(path).read_text(encoding="utf-8")
    return detect_language_from_text(text)


def detect_language_for_document(path: str | Path) -> LanguageDetectionResult:
    source_path = Path(path)
    source_text = source_path.read_text(encoding="utf-8")
    document_type = detect_document_type(source_path)
    if document_type is None:
        return detect_language_from_text(source_text)

    detection_text = get_handler_for_document_type(
        document_type
    ).extract_language_detection_text(source_text)
    return detect_language_from_text(detection_text)


def language_matches_direction(language: str, direction: str) -> bool:
    if direction == "zh_to_en":
        return language == "zh"
    if direction == "en_to_zh":
        return language == "en"
    raise ValueError(f"Unsupported direction: {direction}")


def direction_display_name(direction: str) -> str:
    if direction == "zh_to_en":
        return "中译英"
    if direction == "en_to_zh":
        return "英译中"
    raise ValueError(f"Unsupported direction: {direction}")


def _sanitize_text(text: str) -> str:
    sanitized = text
    sanitized = _CODE_BLOCK_RE.sub(" ", sanitized)
    sanitized = _XML_TAG_RE.sub(" ", sanitized)
    sanitized = _INLINE_CODE_RE.sub(" ", sanitized)
    sanitized = _IMAGE_RE.sub(lambda match: match.group(1), sanitized)
    sanitized = _LINK_RE.sub(lambda match: match.group(1), sanitized)
    sanitized = _URL_RE.sub(" ", sanitized)
    sanitized = _PATHISH_RE.sub(" ", sanitized)
    sanitized = _SPECIAL_MARK_RE.sub(" ", sanitized)
    return sanitized
