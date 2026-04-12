from doc_translation_tool.utils.text_utils import extract_file_references


def test_extract_file_references_trims_common_cjk_trailing_punctuation() -> None:
    text = "请检查 settings.yaml。然后查看 docs/report.dita，最后运行 ./scripts/start.sh。"

    references = extract_file_references(text)

    assert references == [
        (4, 17, "settings.yaml"),
        (23, 39, "docs/report.dita"),
        (45, 63, "./scripts/start.sh"),
    ]


def test_extract_file_references_preserves_positions_for_duplicate_tokens() -> None:
    text = "先复制 boot0.bin，再校验 boot0.bin。"

    references = extract_file_references(text)

    assert references == [
        (4, 13, "boot0.bin"),
        (18, 27, "boot0.bin"),
    ]
