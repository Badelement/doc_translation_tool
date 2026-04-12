from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from doc_translation_tool.config import AppSettings


@dataclass(slots=True)
class DocumentSegment:
    """Single translatable segment generated from a prepared document block."""

    id: str
    block_index: int
    block_type: str
    order_in_block: int
    text: str


@dataclass(slots=True)
class PreparedDocumentBlock:
    """Prepared document block with the segment IDs derived from it."""

    block_index: int
    block_type: str
    protected_text: str
    placeholders: list[Any] = field(default_factory=list)
    segment_ids: list[str] = field(default_factory=list)
    translatable: bool = True
    meta: dict[str, str | int] = field(default_factory=dict)


@dataclass(slots=True)
class PreparedDocument:
    """Format-agnostic document prepared for batch translation."""

    blocks: list[PreparedDocumentBlock]
    segments: list[DocumentSegment]
    trailing_newline: bool = False
    document_type: str = "generic"


class DocumentHandler(ABC):
    """Format-specific adapter between source documents and the translation core."""

    document_type: str

    @abstractmethod
    def prepare_document(
        self,
        source_text: str,
        *,
        settings: AppSettings,
    ) -> PreparedDocument:
        """Extract and protect translatable content from a source document."""

    @abstractmethod
    def rebuild_protected_block_texts(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str] | None = None,
    ) -> list[str]:
        """Rebuild protected block texts from translated segment outputs."""

    @abstractmethod
    def rebuild_document(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str] | None = None,
    ) -> str:
        """Restore a final document string from translated segment outputs."""

    @abstractmethod
    def output_extension(self, source_path: str | Path) -> str:
        """Return the output extension for translated files of this type."""

    def extract_language_detection_text(self, source_text: str) -> str:
        """Return a representative text sample for language detection."""
        return source_text
