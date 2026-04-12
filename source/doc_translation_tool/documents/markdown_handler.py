from __future__ import annotations

from pathlib import Path

from doc_translation_tool.config import AppSettings
from doc_translation_tool.documents.base import DocumentHandler, PreparedDocument
from doc_translation_tool.documents.types import MARKDOWN_DOCUMENT_TYPE
from doc_translation_tool.markdown.parser import MarkdownParser
from doc_translation_tool.markdown.protector import MarkdownProtector
from doc_translation_tool.markdown.rebuilder import MarkdownRebuilder
from doc_translation_tool.markdown.segmenter import MarkdownSegmenter


class MarkdownDocumentHandler(DocumentHandler):
    """Adapter that exposes the existing Markdown flow via the document handler API."""

    document_type = MARKDOWN_DOCUMENT_TYPE

    def __init__(
        self,
        *,
        parser: MarkdownParser | None = None,
        protector: MarkdownProtector | None = None,
        segmenter: MarkdownSegmenter | None = None,
        rebuilder: MarkdownRebuilder | None = None,
    ) -> None:
        self.parser = parser or MarkdownParser()
        self.protector = protector
        self.segmenter = segmenter or MarkdownSegmenter()
        self.rebuilder = rebuilder or MarkdownRebuilder()

    def prepare_document(
        self,
        source_text: str,
        *,
        settings: AppSettings,
    ) -> PreparedDocument:
        document = self.parser.parse(source_text)
        protector = self.protector or MarkdownProtector(
            translatable_front_matter_fields=settings.front_matter_translatable_fields,
        )
        prepared_document = self.segmenter.segment(protector.protect(document))
        prepared_document.document_type = self.document_type
        return prepared_document

    def rebuild_protected_block_texts(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str] | None = None,
    ) -> list[str]:
        return self.rebuilder.rebuild_protected_block_texts(
            document,
            translated_segment_texts,
        )

    def rebuild_document(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str] | None = None,
    ) -> str:
        return self.rebuilder.rebuild_document(document, translated_segment_texts)

    def output_extension(self, source_path: str | Path) -> str:
        suffix = Path(source_path).suffix.lower()
        return suffix or ".md"
