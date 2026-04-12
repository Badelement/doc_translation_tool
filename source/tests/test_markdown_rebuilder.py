from doc_translation_tool.markdown import (
    MarkdownParser,
    MarkdownProtector,
    MarkdownRebuilder,
    MarkdownSegmenter,
)


def test_rebuild_document_restores_placeholders_in_translated_markdown() -> None:
    text = (
        "# Title `code`\n"
        "\n"
        "Paragraph with [docs](https://example.com/doc) and "
        "![diagram](figures/demo.png).\n"
        "\n"
        ":::note\n"
        "Use `demo.sh` before reading [guide](guide.md).\n"
        ":::\n"
        "\n"
        "```bash\n"
        "echo hello\n"
        "```\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=200)
    rebuilder = MarkdownRebuilder()

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    translated_segment_texts = {
        segmented.segments[0].id: "# English Title @@PROTECT_0000@@",
        segmented.segments[1].id: (
            "English paragraph with [docs](@@PROTECT_0001@@) and "
            "![diagram](@@PROTECT_0002@@)."
        ),
        segmented.segments[2].id: (
            ":::note\n"
            "Use @@PROTECT_0003@@ before reading [guide](@@PROTECT_0004@@).\n"
            ":::"
        ),
    }

    rebuilt = rebuilder.rebuild_document(segmented, translated_segment_texts)

    assert rebuilt == (
        "# English Title `code`\n"
        "\n"
        "English paragraph with [docs](https://example.com/doc) and "
        "![diagram](figures/demo.png).\n"
        "\n"
        ":::note\n"
        "Use `demo.sh` before reading [guide](guide.md).\n"
        ":::\n"
        "\n"
        "```bash\n"
        "echo hello\n"
        "```\n"
    )


def test_rebuild_document_without_translated_texts_restores_original_markdown() -> None:
    text = (
        "Paragraph with `inline` and [docs](https://example.com/doc).\n"
        "\n"
        "```python\n"
        "print('hello')\n"
        "```\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=50)
    rebuilder = MarkdownRebuilder()

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    assert rebuilder.rebuild_document(segmented) == text


def test_rebuild_document_restores_translated_table_with_stable_columns() -> None:
    text = (
        "| 名称 | 说明 |\n"
        "| --- | --- |\n"
        "| boot0 | 启动文件 |\n"
    )

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=20)
    rebuilder = MarkdownRebuilder()

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    translated_segment_texts = {
        segmented.segments[0].id: "@@PROTECT_0000@@ Name @@PROTECT_0001@@ Description @@PROTECT_0002@@\n",
        segmented.segments[1].id: "@@PROTECT_0003@@\n",
        segmented.segments[2].id: "@@PROTECT_0004@@ boot0 @@PROTECT_0005@@ Boot file @@PROTECT_0006@@",
    }

    rebuilt = rebuilder.rebuild_document(segmented, translated_segment_texts)

    assert rebuilt == (
        "| Name | Description |\n"
        "| --- | --- |\n"
        "| boot0 | Boot file |\n"
    )
