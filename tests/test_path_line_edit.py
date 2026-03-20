from pathlib import Path

from PySide6.QtCore import QMimeData, QUrl

from doc_translation_tool.ui.path_line_edit import PathLineEdit


def test_extract_markdown_file_from_mime_data(tmp_path: Path) -> None:
    markdown_file = tmp_path / "dropped.md"
    markdown_file.write_text("# dropped\n", encoding="utf-8")

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(markdown_file))])

    extracted = PathLineEdit.extract_path_from_mime_data(
        mime_data,
        "markdown_file",
    )

    assert extracted == str(markdown_file)


def test_extract_directory_from_mime_data(tmp_path: Path) -> None:
    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(tmp_path))])

    extracted = PathLineEdit.extract_path_from_mime_data(
        mime_data,
        "directory",
    )

    assert extracted == str(tmp_path)


def test_extract_rejects_non_markdown_file(tmp_path: Path) -> None:
    text_file = tmp_path / "plain.txt"
    text_file.write_text("plain\n", encoding="utf-8")

    mime_data = QMimeData()
    mime_data.setUrls([QUrl.fromLocalFile(str(text_file))])

    extracted = PathLineEdit.extract_path_from_mime_data(
        mime_data,
        "markdown_file",
    )

    assert extracted is None
