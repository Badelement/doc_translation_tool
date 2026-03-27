from __future__ import annotations

from pathlib import Path

from doc_translation_tool.documents.registry import (
    detect_document_type as _detect_document_type,
    is_supported_document as _is_supported_document,
    source_file_dialog_filter as _source_file_dialog_filter,
    source_path_placeholder_text as _source_path_placeholder_text,
    supported_source_error_message as _supported_source_error_message,
    supported_source_extensions as _supported_source_extensions,
)
from doc_translation_tool.documents.types import DITA_DOCUMENT_TYPE, MARKDOWN_DOCUMENT_TYPE


def detect_document_type(path: str | Path) -> str | None:
    return _detect_document_type(path)


def is_supported_document(path: str | Path) -> bool:
    return _is_supported_document(path)


def supported_source_extensions() -> tuple[str, ...]:
    return _supported_source_extensions()


def supported_source_error_message() -> str:
    return _supported_source_error_message()


def source_file_dialog_filter() -> str:
    return _source_file_dialog_filter()


def source_path_placeholder_text() -> str:
    return _source_path_placeholder_text()
