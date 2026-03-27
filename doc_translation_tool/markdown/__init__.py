"""Markdown processing package."""

from __future__ import annotations

from importlib import import_module


__all__ = [
    "InlineToken",
    "MarkdownProtector",
    "MarkdownRebuilder",
    "MarkdownBlock",
    "MarkdownDocument",
    "MarkdownParser",
    "MarkdownSegmenter",
    "ProtectedMarkdownBlock",
    "ProtectedMarkdownDocument",
    "ProtectedPlaceholder",
    "SegmentedMarkdownBlock",
    "SegmentedMarkdownDocument",
    "TranslationSegment",
]

_EXPORTS = {
    "InlineToken": ("doc_translation_tool.markdown.parser", "InlineToken"),
    "MarkdownBlock": ("doc_translation_tool.markdown.parser", "MarkdownBlock"),
    "MarkdownDocument": ("doc_translation_tool.markdown.parser", "MarkdownDocument"),
    "MarkdownParser": ("doc_translation_tool.markdown.parser", "MarkdownParser"),
    "MarkdownProtector": (
        "doc_translation_tool.markdown.protector",
        "MarkdownProtector",
    ),
    "ProtectedMarkdownBlock": (
        "doc_translation_tool.markdown.protector",
        "ProtectedMarkdownBlock",
    ),
    "ProtectedMarkdownDocument": (
        "doc_translation_tool.markdown.protector",
        "ProtectedMarkdownDocument",
    ),
    "ProtectedPlaceholder": (
        "doc_translation_tool.markdown.protector",
        "ProtectedPlaceholder",
    ),
    "MarkdownRebuilder": (
        "doc_translation_tool.markdown.rebuilder",
        "MarkdownRebuilder",
    ),
    "MarkdownSegmenter": (
        "doc_translation_tool.markdown.segmenter",
        "MarkdownSegmenter",
    ),
    "SegmentedMarkdownBlock": (
        "doc_translation_tool.markdown.segmenter",
        "SegmentedMarkdownBlock",
    ),
    "SegmentedMarkdownDocument": (
        "doc_translation_tool.markdown.segmenter",
        "SegmentedMarkdownDocument",
    ),
    "TranslationSegment": (
        "doc_translation_tool.markdown.segmenter",
        "TranslationSegment",
    ),
}


def __getattr__(name: str):
    try:
        module_path, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}") from exc

    value = getattr(import_module(module_path), attribute_name)
    globals()[name] = value
    return value
