from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from doc_translation_tool.documents.base import DocumentHandler


MARKDOWN_DOCUMENT_TYPE = "markdown"
DITA_DOCUMENT_TYPE = "dita"


@dataclass(frozen=True, slots=True)
class DocumentFormatSpec:
    """Single registered document format and its handler factory."""

    document_type: str
    extensions: tuple[str, ...]
    display_name: str
    handler_factory: Callable[[], DocumentHandler]
