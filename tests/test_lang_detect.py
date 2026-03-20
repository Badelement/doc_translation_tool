from pathlib import Path

from doc_translation_tool.services.lang_detect import (
    detect_language_from_file,
    detect_language_from_text,
    language_matches_direction,
)


def test_detect_language_from_text_returns_zh_for_chinese_text() -> None:
    result = detect_language_from_text("这是一个中文技术文档。它用于说明设备配置和接口行为。")

    assert result.language == "zh"
    assert result.zh_char_count > 0


def test_detect_language_from_text_returns_en_for_english_text() -> None:
    result = detect_language_from_text(
        "This technical document explains the driver configuration and API usage."
    )

    assert result.language == "en"
    assert result.en_word_count > 0


def test_detect_language_from_text_ignores_code_blocks_and_paths() -> None:
    text = """
```bash
make menuconfig
```
See `drivers/media/video.c` for details.
访问路径为 /tmp/demo。
这是中文说明内容，用于确认语言检测不会被代码块干扰。
"""
    result = detect_language_from_text(text)

    assert result.language == "zh"


def test_detect_language_from_file_reads_markdown_file(tmp_path: Path) -> None:
    source_file = tmp_path / "demo.md"
    source_file.write_text(
        "This document describes the PMIC power sequence and driver flow.\n",
        encoding="utf-8",
    )

    result = detect_language_from_file(source_file)

    assert result.language == "en"


def test_language_matches_direction() -> None:
    assert language_matches_direction("zh", "zh_to_en") is True
    assert language_matches_direction("en", "en_to_zh") is True
    assert language_matches_direction("zh", "en_to_zh") is False
