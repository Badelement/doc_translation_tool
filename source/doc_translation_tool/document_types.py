from __future__ import annotations

from doc_translation_tool.documents.registry import (
    detect_document_type,
    is_supported_document,
    source_file_dialog_filter,
    source_path_placeholder_text,
    supported_source_error_message,
    supported_source_extensions,
)
from doc_translation_tool.documents.types import DITA_DOCUMENT_TYPE, MARKDOWN_DOCUMENT_TYPE

__all__ = [
    "DITA_DOCUMENT_TYPE",
    "MARKDOWN_DOCUMENT_TYPE",
    "detect_document_type",
    "is_supported_document",
    "source_file_dialog_filter",
    "source_path_placeholder_text",
    "supported_source_error_message",
    "supported_source_extensions",
]
