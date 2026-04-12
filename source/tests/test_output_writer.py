from pathlib import Path

import pytest

from doc_translation_tool.services import MarkdownOutputWriter, OutputWriteError


def test_build_output_filename_uses_direction_suffixes() -> None:
    writer = MarkdownOutputWriter()

    assert writer.build_output_filename("guide.md", "zh_to_en") == "guide_en.md"
    assert writer.build_output_filename("guide.md", "en_to_zh") == "guide_zh.md"


def test_write_output_writes_utf8_markdown_file(tmp_path: Path) -> None:
    source_file = tmp_path / "guide.md"
    source_file.write_text("# 原文\n", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    writer = MarkdownOutputWriter()
    markdown_text = "# English title\n\nTranslated 内容。\n"

    result = writer.write_output(
        source_path=source_file,
        output_dir=output_dir,
        direction="zh_to_en",
        markdown_text=markdown_text,
    )

    output_path = Path(result.output_path)

    assert output_path.name == "guide_en.md"
    assert output_path.read_bytes() == markdown_text.encode("utf-8")
    assert result.file_name == "guide_en.md"
    assert result.bytes_written == len(markdown_text.encode("utf-8"))


def test_write_output_keeps_source_file_unchanged_when_using_source_directory(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "demo.md"
    source_text = "# 原文\n"
    source_file.write_text(source_text, encoding="utf-8")

    writer = MarkdownOutputWriter()

    result = writer.write_output(
        source_path=source_file,
        output_dir=tmp_path,
        direction="zh_to_en",
        markdown_text="# Translated\n",
    )

    assert source_file.read_text(encoding="utf-8") == source_text
    assert Path(result.output_path) == tmp_path / "demo_en.md"


def test_write_output_overwrites_existing_output_file(tmp_path: Path) -> None:
    source_file = tmp_path / "guide.md"
    source_file.write_text("# 原文\n", encoding="utf-8")
    existing_output = tmp_path / "guide_en.md"
    existing_output.write_text("old\n", encoding="utf-8")

    writer = MarkdownOutputWriter()

    result = writer.write_output(
        source_path=source_file,
        output_dir=tmp_path,
        direction="zh_to_en",
        markdown_text="new\n",
    )

    assert existing_output.read_text(encoding="utf-8") == "new\n"
    assert Path(result.output_path) == existing_output


def test_write_output_rejects_unknown_direction(tmp_path: Path) -> None:
    source_file = tmp_path / "guide.md"
    source_file.write_text("# 原文\n", encoding="utf-8")

    writer = MarkdownOutputWriter()

    with pytest.raises(OutputWriteError, match="Unsupported translation direction"):
        writer.write_output(
            source_path=source_file,
            output_dir=tmp_path,
            direction="zh_to_jp",
            markdown_text="text\n",
        )
