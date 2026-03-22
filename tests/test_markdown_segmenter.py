from doc_translation_tool.markdown import MarkdownParser, MarkdownProtector, MarkdownSegmenter


def test_segment_short_paragraph_as_single_segment() -> None:
    text = "短文本，不需要切分。"

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=100)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    assert len(segmented.segments) == 1
    assert segmented.segments[0].text == text


def test_segment_chinese_text_by_sentence_when_length_requires_split() -> None:
    text = "第一句比较短。第二句也比较短。第三句继续说明。"

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=12)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    assert len(segmented.segments) >= 2
    assert "".join(segment.text for segment in segmented.segments) == text


def test_segment_english_text_by_sentence_when_length_requires_split() -> None:
    text = (
        "The first sentence is short. "
        "The second sentence is also short. "
        "The third sentence continues."
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=40)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    assert len(segmented.segments) >= 2
    assert "".join(segment.text for segment in segmented.segments) == text


def test_segment_non_translatable_code_block_as_zero_segments() -> None:
    text = "```bash\necho hello\n```\n"

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=10)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    assert len(segmented.blocks) == 1
    assert segmented.blocks[0].segment_ids == []
    assert segmented.segments == []


def test_segment_preserves_protected_placeholders() -> None:
    text = "Use `make menuconfig` and [docs](https://example.com/doc)."

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=25)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    combined = "".join(segment.text for segment in segmented.segments)
    assert "@@PROTECT_" in combined
    assert "https://example.com/doc" not in combined
    assert "`make menuconfig`" not in combined


def test_rebuild_protected_block_texts_uses_translated_segment_map() -> None:
    text = "# 标题 `code`\n"

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=100)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)
    translated = {segmented.segments[0].id: "# Translated @@PROTECT_0000@@"}

    rebuilt_blocks = segmenter.rebuild_protected_block_texts(segmented, translated)

    assert rebuilt_blocks == ["# Translated @@PROTECT_0000@@"]


def test_segment_realistic_sample_rebuilds_original_protected_texts() -> None:
    text = (
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
    segmenter = MarkdownSegmenter(max_segment_length=20)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)
    rebuilt_blocks = segmenter.rebuild_protected_block_texts(segmented)

    assert rebuilt_blocks == [block.protected_text for block in protected.blocks]


def test_segment_table_by_packed_lines_to_reduce_request_count() -> None:
    text = (
        "| 名称 | 说明 |\n"
        "| --- | --- |\n"
        "| boot0 | 启动文件 |\n"
        "| env | 环境配置 |\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=150)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    assert len(segmented.blocks) == 1
    assert segmented.blocks[0].block_type == "table"
    assert len(segmented.segments) == 2
    assert segmented.segments[0].text.count("\n") >= 1
    assert "".join(segment.text for segment in segmented.segments) == protected.blocks[0].protected_text


def test_segment_long_table_line_by_html_breaks_without_exceeding_limit() -> None:
    text = (
        "| 类型 | 格式 |\n"
        "| --- | --- |\n"
        "| Bayer RAW | V4L2_PIX_FMT_SBGGR16 <br> V4L2_PIX_FMT_SGBRG16 <br> "
        "V4L2_PIX_FMT_SGRBG16 <br> V4L2_PIX_FMT_SRGGB16 <br> "
        "V4L2_PIX_FMT_SBGGR14 <br> V4L2_PIX_FMT_SGBRG14 |\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=80)

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    assert len(segmented.blocks) == 1
    assert segmented.blocks[0].block_type == "table"
    assert len(segmented.segments) >= 3
    assert all(len(segment.text) <= 80 for segment in segmented.segments)
    assert "".join(segment.text for segment in segmented.segments) == protected.blocks[0].protected_text
