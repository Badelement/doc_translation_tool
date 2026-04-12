from pathlib import Path

from doc_translation_tool.services.validator import (
    validate_batch_translation_inputs,
    validate_multi_file_translation_inputs,
    validate_translation_inputs,
)


def test_validate_translation_inputs_accepts_valid_markdown_and_output_dir(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "demo.md"
    source_file.write_text("# demo\n", encoding="utf-8")

    result = validate_translation_inputs(str(source_file), str(tmp_path))

    assert result.valid is True
    assert result.source_path == str(source_file)
    assert result.output_dir == str(tmp_path)
    assert result.errors == []


def test_validate_translation_inputs_accepts_valid_dita_and_output_dir(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "demo.dita"
    source_file.write_text("<topic id='demo'><title>标题</title></topic>\n", encoding="utf-8")

    result = validate_translation_inputs(str(source_file), str(tmp_path))

    assert result.valid is True
    assert result.source_path == str(source_file)
    assert result.output_dir == str(tmp_path)
    assert result.errors == []


def test_validate_translation_inputs_auto_fills_output_dir(tmp_path: Path) -> None:
    source_file = tmp_path / "demo.md"
    source_file.write_text("# demo\n", encoding="utf-8")

    result = validate_translation_inputs(str(source_file), "")

    assert result.valid is True
    assert result.output_dir == str(tmp_path)
    assert result.auto_filled_output_dir is True


def test_validate_translation_inputs_rejects_missing_source() -> None:
    result = validate_translation_inputs("", "")

    assert result.valid is False
    assert "目标翻译文件不能为空" in result.errors


def test_validate_translation_inputs_rejects_non_markdown_file(tmp_path: Path) -> None:
    source_file = tmp_path / "demo.txt"
    source_file.write_text("demo\n", encoding="utf-8")

    result = validate_translation_inputs(str(source_file), str(tmp_path))

    assert result.valid is False
    assert "目标翻译文件必须为 .dita 或 .md 格式" in result.errors


def test_validate_batch_translation_inputs_accepts_valid_source_dir(
    tmp_path: Path,
) -> None:
    result = validate_batch_translation_inputs(str(tmp_path), str(tmp_path))

    assert result.valid is True
    assert result.source_path == str(tmp_path)
    assert result.output_dir == str(tmp_path)


def test_validate_batch_translation_inputs_rejects_missing_source_dir() -> None:
    result = validate_batch_translation_inputs("", "")

    assert result.valid is False
    assert "批量翻译源目录不能为空" in result.errors


def test_validate_batch_translation_inputs_rejects_file_source_path(
    tmp_path: Path,
) -> None:
    source_file = tmp_path / "demo.md"
    source_file.write_text("# demo\n", encoding="utf-8")

    result = validate_batch_translation_inputs(str(source_file), str(tmp_path))

    assert result.valid is False
    assert "批量翻译源路径必须为文件夹路径" in result.errors


def test_validate_multi_file_translation_inputs_accepts_supported_files(
    tmp_path: Path,
) -> None:
    source_one = tmp_path / "a.md"
    source_two = tmp_path / "b.dita"
    source_one.write_text("# a\n", encoding="utf-8")
    source_two.write_text("<topic id='b'><title>B</title></topic>\n", encoding="utf-8")

    result = validate_multi_file_translation_inputs(
        [str(source_one), str(source_two)],
        str(tmp_path),
    )

    assert result.valid is True
    assert result.source_paths == [str(source_one), str(source_two)]
    assert result.output_dir == str(tmp_path)


def test_validate_multi_file_translation_inputs_rejects_empty_source_list(
    tmp_path: Path,
) -> None:
    result = validate_multi_file_translation_inputs([], str(tmp_path))

    assert result.valid is False
    assert "多文件任务源文件不能为空" in result.errors
