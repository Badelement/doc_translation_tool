from doc_translation_tool.document_types import (
    DITA_DOCUMENT_TYPE,
    MARKDOWN_DOCUMENT_TYPE,
    detect_document_type,
    is_supported_document,
    source_file_dialog_filter,
    source_path_placeholder_text,
    supported_source_extensions,
    supported_source_error_message,
)


def test_detect_document_type_recognizes_markdown() -> None:
    assert detect_document_type("topic.dita") == DITA_DOCUMENT_TYPE
    assert detect_document_type("guide.md") == MARKDOWN_DOCUMENT_TYPE
    assert detect_document_type("GUIDE.MD") == MARKDOWN_DOCUMENT_TYPE


def test_detect_document_type_rejects_unsupported_extensions() -> None:
    assert detect_document_type("guide.txt") is None
    assert is_supported_document("guide.txt") is False


def test_supported_source_extensions_reports_current_builtin_types() -> None:
    assert supported_source_extensions() == (".dita", ".md")


def test_supported_source_messages_match_current_multi_format_behavior() -> None:
    assert supported_source_error_message() == "目标翻译文件必须为 .dita 或 .md 格式"
    assert source_file_dialog_filter() == "Supported Documents (*.dita *.md)"
    assert source_path_placeholder_text() == "请选择、拖入或粘贴支持的文档路径"
