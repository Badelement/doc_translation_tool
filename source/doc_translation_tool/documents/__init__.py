"""Document handlers and shared document abstractions."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING

from doc_translation_tool.documents.base import (
    DocumentHandler,
    DocumentSegment,
    PreparedDocument,
    PreparedDocumentBlock,
)
from doc_translation_tool.documents.types import (
    DITA_DOCUMENT_TYPE,
    MARKDOWN_DOCUMENT_TYPE,
    DocumentFormatSpec,
)

if TYPE_CHECKING:
    from doc_translation_tool.documents.dita_handler import DitaDocumentHandler
    from doc_translation_tool.documents.markdown_handler import MarkdownDocumentHandler

__all__ = [
    "detect_document_type",
    "DocumentHandler",
    "DocumentFormatSpec",
    "DocumentSegment",
    "DITA_DOCUMENT_TYPE",
    "DitaDocumentHandler",
    "get_document_format_spec",
    "PreparedDocument",
    "PreparedDocumentBlock",
    "is_supported_document",
    "iter_registered_document_formats",
    "MARKDOWN_DOCUMENT_TYPE",
    "MarkdownDocumentHandler",
    "get_handler_for_document_type",
    "register_document_format",
    "source_file_dialog_filter",
    "source_path_placeholder_text",
    "supported_source_error_message",
    "supported_source_extensions",
    "unregister_document_format",
]

_LAZY_EXPORTS = {
    "DitaDocumentHandler": "doc_translation_tool.documents.dita_handler",
    "MarkdownDocumentHandler": "doc_translation_tool.documents.markdown_handler",
    "detect_document_type": "doc_translation_tool.documents.registry",
    "get_document_format_spec": "doc_translation_tool.documents.registry",
    "get_handler_for_document_type": "doc_translation_tool.documents.registry",
    "is_supported_document": "doc_translation_tool.documents.registry",
    "iter_registered_document_formats": "doc_translation_tool.documents.registry",
    "register_document_format": "doc_translation_tool.documents.registry",
    "source_file_dialog_filter": "doc_translation_tool.documents.registry",
    "source_path_placeholder_text": "doc_translation_tool.documents.registry",
    "supported_source_error_message": "doc_translation_tool.documents.registry",
    "supported_source_extensions": "doc_translation_tool.documents.registry",
    "unregister_document_format": "doc_translation_tool.documents.registry",
}


def __getattr__(name: str):
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

    module = import_module(module_name)
    value = getattr(module, name)
    globals()[name] = value
    return value
