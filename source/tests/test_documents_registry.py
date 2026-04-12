from pathlib import Path

from doc_translation_tool.config import AppSettings, LLMSettings
from doc_translation_tool.document_types import (
    DITA_DOCUMENT_TYPE,
    MARKDOWN_DOCUMENT_TYPE,
    detect_document_type,
    supported_source_extensions,
)
from doc_translation_tool.documents import (
    DocumentFormatSpec,
    DocumentHandler,
    DocumentSegment,
    DitaDocumentHandler,
    MarkdownDocumentHandler,
    PreparedDocument,
    PreparedDocumentBlock,
    get_handler_for_document_type,
    register_document_format,
    unregister_document_format,
)


def _build_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=str(tmp_path),
        llm=LLMSettings(
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="test-model",
        ),
    )


def test_registry_returns_markdown_handler_for_markdown_document_type() -> None:
    handler = get_handler_for_document_type(MARKDOWN_DOCUMENT_TYPE)

    assert isinstance(handler, MarkdownDocumentHandler)


def test_registry_returns_dita_handler_for_dita_document_type() -> None:
    handler = get_handler_for_document_type(DITA_DOCUMENT_TYPE)

    assert isinstance(handler, DitaDocumentHandler)


def test_markdown_handler_prepares_markdown_document_with_markdown_type(
    tmp_path: Path,
) -> None:
    handler = MarkdownDocumentHandler()

    prepared = handler.prepare_document(
        "# 标题\n\n这是一个测试。\n",
        settings=_build_settings(tmp_path),
    )

    assert prepared.document_type == MARKDOWN_DOCUMENT_TYPE
    assert len(prepared.blocks) >= 1
    assert len(prepared.segments) >= 1


def test_registry_allows_registering_future_document_formats() -> None:
    class AsciiDocHandler(DocumentHandler):
        document_type = "asciidoc"

        def prepare_document(self, source_text: str, *, settings: AppSettings) -> PreparedDocument:
            del source_text
            del settings
            return PreparedDocument(
                blocks=[
                    PreparedDocumentBlock(
                        block_index=0,
                        block_type="paragraph",
                    )
                ],
                segments=[
                    DocumentSegment(
                        id="asciidoc_seg_0000",
                        block_index=0,
                        block_type="paragraph",
                        order_in_block=0,
                        text="demo",
                    )
                ],
                document_type=self.document_type,
            )

        def rebuild_protected_block_texts(
            self,
            document: PreparedDocument,
            translated_segment_texts: dict[str, str] | None = None,
        ) -> list[str]:
            del document
            del translated_segment_texts
            return ["demo"]

        def rebuild_document(
            self,
            document: PreparedDocument,
            translated_segment_texts: dict[str, str] | None = None,
        ) -> str:
            del document
            del translated_segment_texts
            return "demo"

        def output_extension(self, source_path: str | Path) -> str:
            del source_path
            return ".adoc"

    try:
        register_document_format(
            DocumentFormatSpec(
                document_type="asciidoc",
                extensions=(".adoc",),
                display_name="AsciiDoc",
                handler_factory=AsciiDocHandler,
            )
        )

        assert detect_document_type("guide.adoc") == "asciidoc"
        assert ".adoc" in supported_source_extensions()
        assert isinstance(get_handler_for_document_type("asciidoc"), AsciiDocHandler)
    finally:
        unregister_document_format("asciidoc")

    assert detect_document_type("guide.adoc") is None
