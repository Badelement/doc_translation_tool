from doc_translation_tool.markdown.parser import MarkdownParser


def test_parse_front_matter_and_heading() -> None:
    text = (
        "---\n"
        "title: Demo\n"
        "---\n"
        "\n"
        "# Heading\n"
    )

    document = MarkdownParser().parse(text)

    assert [block.type for block in document.blocks] == [
        "front_matter",
        "blank_line",
        "heading",
    ]
    assert document.blocks[2].meta["level"] == 1


def test_parse_fenced_code_block_and_paragraph() -> None:
    text = (
        "Before code.\n"
        "\n"
        "```bash\n"
        "echo hello\n"
        "```\n"
        "\n"
        "After code.\n"
    )

    document = MarkdownParser().parse(text)

    assert [block.type for block in document.blocks] == [
        "paragraph",
        "blank_line",
        "fenced_code_block",
        "blank_line",
        "paragraph",
    ]
    assert "echo hello" in document.blocks[2].raw_text


def test_parse_admonition_block() -> None:
    text = (
        ":::note\n"
        "Keep this note body.\n"
        ":::\n"
    )

    document = MarkdownParser().parse(text)

    assert len(document.blocks) == 1
    assert document.blocks[0].type == "admonition"
    assert document.blocks[0].meta["admonition_type"] == "note"


def test_parse_inline_tokens_for_link_image_and_inline_code() -> None:
    text = (
        "Use `make menuconfig` and see "
        "[documentation](https://example.com) with "
        "![示意图](figures/demo.png)."
    )

    document = MarkdownParser().parse(text)
    block = document.blocks[0]

    assert block.type == "paragraph"
    assert [token.type for token in block.inline_tokens] == [
        "text",
        "inline_code",
        "text",
        "link",
        "text",
        "image",
        "text",
    ]
    assert block.inline_tokens[1].text == "make menuconfig"
    assert block.inline_tokens[3].target == "https://example.com"
    assert block.inline_tokens[5].target == "figures/demo.png"


def test_parse_inline_code_with_multi_backtick_delimiter() -> None:
    text = (
        "v853中安全和非安全方案的```CONFIG_SPINOR_LOGICAL_OFFSET```不同，"
        "需根据```bootpackage```的大小进行动态适配。"
    )

    document = MarkdownParser().parse(text)
    block = document.blocks[0]

    assert [token.type for token in block.inline_tokens] == [
        "text",
        "inline_code",
        "text",
        "inline_code",
        "text",
    ]
    assert block.inline_tokens[1].raw == "```CONFIG_SPINOR_LOGICAL_OFFSET```"
    assert block.inline_tokens[1].text == "CONFIG_SPINOR_LOGICAL_OFFSET"
    assert block.inline_tokens[3].raw == "```bootpackage```"
    assert block.inline_tokens[3].text == "bootpackage"


def test_parse_table_block() -> None:
    text = (
        "| Name | Value |\n"
        "| --- | --- |\n"
        "| mode | test |\n"
        "| lang | zh |\n"
    )

    document = MarkdownParser().parse(text)

    assert len(document.blocks) == 1
    assert document.blocks[0].type == "table"
    assert len(document.blocks[0].lines) == 4


def test_parse_list_item_blocks() -> None:
    text = (
        "- first item\n"
        "1. second item\n"
    )

    document = MarkdownParser().parse(text)

    assert [block.type for block in document.blocks] == ["list_item", "list_item"]


def test_parse_realistic_sample_with_multiple_block_types() -> None:
    text = (
        "---\n"
        "title: Demo\n"
        "---\n"
        "\n"
        "# 标题\n"
        "\n"
        "普通段落，包含 ![图片](figures/a.png) 和 `inline code`。\n"
        "\n"
        ":::warning\n"
        "警告内容\n"
        ":::\n"
        "\n"
        "```python\n"
        "print('hello')\n"
        "```\n"
    )

    document = MarkdownParser().parse(text)

    assert [block.type for block in document.blocks] == [
        "front_matter",
        "blank_line",
        "heading",
        "blank_line",
        "paragraph",
        "blank_line",
        "admonition",
        "blank_line",
        "fenced_code_block",
    ]
