from doc_translation_tool.markdown import MarkdownParser, MarkdownProtector


def test_protect_and_restore_inline_code_and_targets() -> None:
    text = (
        "Use `make menuconfig`, see [docs](https://example.com/doc), "
        "and check ![示意图](figures/demo.png)."
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    assert len(protected.blocks) == 1
    block = protected.blocks[0]
    assert block.block_type == "paragraph"
    assert "@@PROTECT_" in block.protected_text
    assert "https://example.com/doc" not in block.protected_text
    assert "figures/demo.png" not in block.protected_text
    assert "`make menuconfig`" not in block.protected_text

    restored = protector.restore_document(protected)

    assert restored == text


def test_protect_fenced_code_block_as_single_placeholder() -> None:
    text = (
        "```bash\n"
        "echo hello\n"
        "```\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    block = protected.blocks[0]
    assert block.block_type == "fenced_code_block"
    assert block.translatable is False
    assert block.protected_text.startswith("@@PROTECT_")
    assert protector.restore_document(protected) == text


def test_protect_admonition_preserves_markers_and_restores_inline_code() -> None:
    text = (
        ":::note\n"
        "Use `demo.sh` in the note body.\n"
        ":::\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    block = protected.blocks[0]
    assert block.block_type == "admonition"
    assert block.protected_text.startswith(":::note\n")
    assert block.protected_text.endswith("\n:::")
    assert "`demo.sh`" not in block.protected_text
    assert protector.restore_document(protected) == text


def test_protect_triple_backtick_inline_code_without_swallowing_surrounding_text() -> None:
    text = (
        "v853中安全和非安全方案的```CONFIG_SPINOR_LOGICAL_OFFSET```不同，"
        "需根据```bootpackage```的大小进行动态适配。\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    block = protected.blocks[0]
    assert block.protected_text == (
        "v853中安全和非安全方案的@@PROTECT_0000@@不同，"
        "需根据@@PROTECT_0001@@的大小进行动态适配。"
    )
    assert protector.restore_document(protected) == text


def test_restore_document_with_translated_block_texts_keeps_placeholders_safe() -> None:
    text = "# 标题 `inline`\n"

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    translated_texts = ["# Translated title @@PROTECT_0000@@"]
    restored = protector.restore_document(protected, translated_texts)

    assert restored == "# Translated title `inline`\n"


def test_protect_realistic_sample_restores_original_document() -> None:
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
        "警告内容，参考 [文档](https://example.com/doc)\n"
        ":::\n"
        "\n"
        "```python\n"
        "print('hello')\n"
        "```\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    assert protector.restore_document(protected) == text


def test_protect_table_preserves_separator_and_pipe_structure() -> None:
    text = (
        "| 名称 | 说明 |\n"
        "| --- | --- |\n"
        "| boot0 | 启动文件 |\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    assert len(protected.blocks) == 1
    block = protected.blocks[0]

    assert block.block_type == "table"
    assert block.translatable is True
    assert "| --- | --- |" not in block.protected_text
    assert block.protected_text.count("@@PROTECT_") >= 5
    assert protector.restore_document(protected) == text


def test_restore_table_keeps_column_count_and_inline_targets() -> None:
    text = (
        "| 名称 | 说明 |\n"
        "| --- | --- |\n"
        "| [文档](guide.md) | 使用 `boot0` |\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    translated_texts = [
        "@@PROTECT_0000@@ Name @@PROTECT_0001@@ Description @@PROTECT_0002@@\n"
        "@@PROTECT_0003@@\n"
        "@@PROTECT_0004@@ [Docs](@@PROTECT_0005@@) @@PROTECT_0006@@ Use @@PROTECT_0007@@ @@PROTECT_0008@@"
    ]

    restored = protector.restore_document(protected, translated_texts)

    assert restored == (
        "| Name | Description |\n"
        "| --- | --- |\n"
        "| [Docs](guide.md) | Use `boot0` |\n"
    )


def test_protect_front_matter_translates_only_allowed_scalar_fields() -> None:
    text = (
        "---\n"
        "title: 示例标题\n"
        "subtitle: 示例副标题\n"
        "author: 张三\n"
        "date: 2026-03-20\n"
        "ver: v1.0\n"
        "---\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    assert len(protected.blocks) == 1
    block = protected.blocks[0]

    assert block.block_type == "front_matter"
    assert block.translatable is True
    assert "title: 示例标题" not in block.protected_text
    assert "subtitle: 示例副标题" not in block.protected_text
    assert "author: 张三" not in block.protected_text
    assert "date: 2026-03-20" not in block.protected_text
    assert "ver: v1.0" not in block.protected_text
    assert protector.restore_document(protected) == text


def test_restore_front_matter_keeps_keys_and_non_translatable_fields_unchanged() -> None:
    text = (
        "---\n"
        "title: 示例标题\n"
        "subtitle: 示例副标题\n"
        "author: 张三\n"
        "---\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)

    translated_texts = [
        "---\n"
        "@@PROTECT_0000@@Translated Title\n"
        "@@PROTECT_0001@@Translated Subtitle\n"
        "@@PROTECT_0002@@\n"
        "---"
    ]

    restored = protector.restore_document(protected, translated_texts)

    assert restored == (
        "---\n"
        "title: Translated Title\n"
        "subtitle: Translated Subtitle\n"
        "author: 张三\n"
        "---\n"
    )


def test_protect_paragraph_embedded_html_xml_tags_but_keep_surrounding_text() -> None:
    text = '请检查 <platform_info> 与 <dump dirpath="out/"/> 配置。\n'

    parser = MarkdownParser()
    protector = MarkdownProtector()
    protected = protector.protect(parser.parse(text))

    assert len(protected.blocks) == 1
    block = protected.blocks[0]
    assert block.block_type == "paragraph"
    assert block.translatable is True
    assert "<platform_info>" not in block.protected_text
    assert '<dump dirpath="out/"/>' not in block.protected_text
    assert block.protected_text.count("@@PROTECT_") >= 2
    assert "请检查 " in block.protected_text
    assert " 配置。" in block.protected_text
    assert protector.restore_document(protected) == text


def test_protect_table_keeps_html_break_tags_visible_for_segment_splitting() -> None:
    text = (
        "| 类型 | 格式 |\n"
        "| --- | --- |\n"
        "| Bayer RAW | V4L2_PIX_FMT_SBGGR16 <br> V4L2_PIX_FMT_SGBRG16 |\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    protected = protector.protect(parser.parse(text))

    assert len(protected.blocks) == 1
    block = protected.blocks[0]
    assert block.block_type == "table"
    assert "<br>" in block.protected_text
    assert protector.restore_document(protected) == text


def test_protect_paragraph_embedded_paths_and_filenames() -> None:
    text = (
        "请修改 board.dts 并执行 ./build.sh，然后检查 "
        "/device/config/chips/{IC}/configs/{BOARD}/{KERNEL_VERSION}/board.dts。\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    protected = protector.protect(parser.parse(text))

    assert len(protected.blocks) == 1
    block = protected.blocks[0]
    assert block.block_type == "paragraph"
    assert "board.dts" not in block.protected_text
    assert "./build.sh" not in block.protected_text
    assert "/device/config/chips/{IC}/configs/{BOARD}/{KERNEL_VERSION}/board.dts" not in block.protected_text
    assert block.protected_text.count("@@PROTECT_") >= 3
    assert protector.restore_document(protected) == text


def test_protect_paragraph_does_not_treat_fraction_like_path() -> None:
    text = "支持 1/2 分频和 3/4 模式。\n"

    parser = MarkdownParser()
    protector = MarkdownProtector()
    protected = protector.protect(parser.parse(text))

    assert len(protected.blocks) == 1
    block = protected.blocks[0]
    assert block.block_type == "paragraph"
    assert "1/2" in block.protected_text
    assert "3/4" in block.protected_text
    assert block.protected_text.count("@@PROTECT_") == 0
    assert protector.restore_document(protected) == text


def test_protect_paragraph_upper_constant_literals() -> None:
    text = "请保持 GPIO_ACTIVE_LOW 和 POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT 不变。\n"

    parser = MarkdownParser()
    protector = MarkdownProtector()
    protected = protector.protect(parser.parse(text))

    assert len(protected.blocks) == 1
    block = protected.blocks[0]
    assert block.block_type == "paragraph"
    assert "GPIO_ACTIVE_LOW" not in block.protected_text
    assert "POWER_SUPPLY_PROP_INPUT_CURRENT_LIMIT" not in block.protected_text
    assert block.protected_text.count("@@PROTECT_") >= 2
    assert protector.restore_document(protected) == text


def test_protect_paragraph_does_not_overprotect_short_uppercase_words() -> None:
    text = "RTC 模块和 PMIC 说明需要翻译。\n"

    parser = MarkdownParser()
    protector = MarkdownProtector()
    protected = protector.protect(parser.parse(text))

    assert len(protected.blocks) == 1
    block = protected.blocks[0]
    assert block.block_type == "paragraph"
    assert "RTC" in block.protected_text
    assert "PMIC" in block.protected_text
    assert protector.restore_document(protected) == text


def test_protect_front_matter_multiline_field_only_exposes_allowed_body_content() -> None:
    text = (
        "---\n"
        "title: 示例标题\n"
        "desc: |\n"
        "  第一行说明\n"
        "\n"
        "  第二行说明\n"
        "author: 张三\n"
        "notes: |\n"
        "  保持原样\n"
        "---\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    document = parser.parse(text)
    protected = protector.protect(document)
    block = protected.blocks[0]

    assert block.block_type == "front_matter"
    assert block.translatable is True
    assert "desc: |" not in block.protected_text
    assert "notes: |" not in block.protected_text
    assert "  保持原样" not in block.protected_text
    assert "第一行说明" in block.protected_text
    assert "第二行说明" in block.protected_text

    translated_texts = [
        "---\n"
        "@@PROTECT_0000@@Translated Title\n"
        "@@PROTECT_0001@@\n"
        "@@PROTECT_0002@@First line\n"
        "@@PROTECT_0003@@\n"
        "@@PROTECT_0004@@Second line\n"
        "@@PROTECT_0005@@\n"
        "@@PROTECT_0006@@\n"
        "@@PROTECT_0007@@\n"
        "---"
    ]

    restored = protector.restore_document(protected, translated_texts)

    assert restored == (
        "---\n"
        "title: Translated Title\n"
        "desc: |\n"
        "  First line\n"
        "\n"
        "  Second line\n"
        "author: 张三\n"
        "notes: |\n"
        "  保持原样\n"
        "---\n"
    )
