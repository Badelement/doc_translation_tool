from pathlib import Path

import pytest

from doc_translation_tool.services import load_glossary


def test_load_glossary_returns_empty_list_when_file_missing(tmp_path: Path) -> None:
    assert load_glossary(tmp_path / "glossary.json") == []


def test_load_glossary_reads_source_target_pairs(tmp_path: Path) -> None:
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text(
        (
            "[\n"
            '  {"source": "远程处理音效", "target": "remote sound effect"},\n'
            '  {"source": "AACT上位机", "target": "AACT host tool"}\n'
            "]\n"
        ),
        encoding="utf-8",
    )

    glossary = load_glossary(glossary_file)

    assert glossary == [
        {"source": "远程处理音效", "target": "remote sound effect"},
        {"source": "AACT上位机", "target": "AACT host tool"},
    ]


def test_load_glossary_rejects_invalid_items(tmp_path: Path) -> None:
    glossary_file = tmp_path / "glossary.json"
    glossary_file.write_text('[{"source": "Android13"}]\n', encoding="utf-8")

    with pytest.raises(ValueError, match="target"):
        load_glossary(glossary_file)
