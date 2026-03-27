from __future__ import annotations

from pathlib import Path

from doc_translation_tool.documents.base import DocumentHandler
from doc_translation_tool.documents.dita_handler import DitaDocumentHandler
from doc_translation_tool.documents.markdown_handler import MarkdownDocumentHandler
from doc_translation_tool.documents.types import (
    DITA_DOCUMENT_TYPE,
    MARKDOWN_DOCUMENT_TYPE,
    DocumentFormatSpec,
)

_DOCUMENT_FORMATS_BY_TYPE: dict[str, DocumentFormatSpec] = {}
_DOCUMENT_TYPES_BY_EXTENSION: dict[str, str] = {}


def register_document_format(
    spec: DocumentFormatSpec,
    *,
    replace: bool = False,
) -> None:
    normalized_extensions = _normalize_extensions(spec.extensions)
    existing_spec = _DOCUMENT_FORMATS_BY_TYPE.get(spec.document_type)
    if existing_spec is not None and not replace:
        raise ValueError(f"Document type already registered: {spec.document_type}")

    conflicting_extensions = [
        extension
        for extension in normalized_extensions
        if extension in _DOCUMENT_TYPES_BY_EXTENSION
        and _DOCUMENT_TYPES_BY_EXTENSION[extension] != spec.document_type
    ]
    if conflicting_extensions and not replace:
        extensions_display = ", ".join(conflicting_extensions)
        raise ValueError(f"Document extensions already registered: {extensions_display}")

    if existing_spec is not None:
        for extension in existing_spec.extensions:
            _DOCUMENT_TYPES_BY_EXTENSION.pop(extension, None)

    registered_spec = DocumentFormatSpec(
        document_type=spec.document_type,
        extensions=normalized_extensions,
        display_name=spec.display_name.strip(),
        handler_factory=spec.handler_factory,
    )
    _DOCUMENT_FORMATS_BY_TYPE[registered_spec.document_type] = registered_spec
    for extension in registered_spec.extensions:
        _DOCUMENT_TYPES_BY_EXTENSION[extension] = registered_spec.document_type


def unregister_document_format(document_type: str) -> DocumentFormatSpec | None:
    spec = _DOCUMENT_FORMATS_BY_TYPE.pop(document_type, None)
    if spec is None:
        return None
    for extension in spec.extensions:
        _DOCUMENT_TYPES_BY_EXTENSION.pop(extension, None)
    return spec


def get_handler_for_document_type(document_type: str) -> DocumentHandler:
    spec = get_document_format_spec(document_type)
    return spec.handler_factory()


def get_document_format_spec(document_type: str) -> DocumentFormatSpec:
    try:
        return _DOCUMENT_FORMATS_BY_TYPE[document_type]
    except KeyError as exc:
        raise ValueError(f"Unsupported document type: {document_type}") from exc


def detect_document_type(path: str | Path) -> str | None:
    return _DOCUMENT_TYPES_BY_EXTENSION.get(Path(path).suffix.lower())


def is_supported_document(path: str | Path) -> bool:
    return detect_document_type(path) is not None


def iter_registered_document_formats() -> tuple[DocumentFormatSpec, ...]:
    return tuple(
        _DOCUMENT_FORMATS_BY_TYPE[document_type]
        for document_type in sorted(_DOCUMENT_FORMATS_BY_TYPE)
    )


def supported_source_extensions() -> tuple[str, ...]:
    return tuple(sorted(_DOCUMENT_TYPES_BY_EXTENSION))


def supported_source_error_message() -> str:
    extensions = supported_source_extensions()
    if len(extensions) == 1:
        return f"目标翻译文件必须为 {extensions[0]} 格式"
    return "目标翻译文件必须为 " + " 或 ".join(extensions) + " 格式"


def source_file_dialog_filter() -> str:
    formats = iter_registered_document_formats()
    extensions = supported_source_extensions()
    if len(formats) == 1 and len(extensions) == 1:
        format_spec = formats[0]
        return f"{format_spec.display_name} Files (*{extensions[0]})"

    wildcard = " ".join(f"*{extension}" for extension in extensions)
    return f"Supported Documents ({wildcard})"


def source_path_placeholder_text() -> str:
    extensions = supported_source_extensions()
    if len(extensions) == 1:
        return f"请选择、拖入或粘贴 {extensions[0]} 文件路径"
    return "请选择、拖入或粘贴支持的文档路径"


def _normalize_extensions(extensions: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for extension in extensions:
        candidate = extension.strip().lower()
        if not candidate:
            raise ValueError("Document extension must not be empty.")
        if not candidate.startswith("."):
            candidate = f".{candidate}"
        if candidate not in normalized:
            normalized.append(candidate)
    if not normalized:
        raise ValueError("Document format must register at least one extension.")
    return tuple(normalized)


register_document_format(
    DocumentFormatSpec(
        document_type=MARKDOWN_DOCUMENT_TYPE,
        extensions=(".md",),
        display_name="Markdown",
        handler_factory=MarkdownDocumentHandler,
    )
)
register_document_format(
    DocumentFormatSpec(
        document_type=DITA_DOCUMENT_TYPE,
        extensions=(".dita",),
        display_name="DITA",
        handler_factory=DitaDocumentHandler,
    )
)
