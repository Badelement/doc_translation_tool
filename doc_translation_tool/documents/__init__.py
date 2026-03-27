"""Document handlers and shared document abstractions."""

from doc_translation_tool.documents.base import (
    DocumentHandler,
    DocumentParseError,
    DocumentSegment,
    PreparedDocument,
    PreparedDocumentBlock,
)
from doc_translation_tool.documents.dita_handler import DitaDocumentHandler
from doc_translation_tool.documents.markdown_handler import MarkdownDocumentHandler
from doc_translation_tool.documents.registry import (
    detect_document_type,
    get_document_format_spec,
    get_handler_for_document_type,
    is_supported_document,
    iter_registered_document_formats,
    register_document_format,
    source_file_dialog_filter,
    source_path_placeholder_text,
    supported_source_error_message,
    supported_source_extensions,
    unregister_document_format,
)
from doc_translation_tool.documents.types import (
    DITA_DOCUMENT_TYPE,
    MARKDOWN_DOCUMENT_TYPE,
    DocumentFormatSpec,
)

__all__ = [
    "detect_document_type",
    "DocumentHandler",
    "DocumentParseError",
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
