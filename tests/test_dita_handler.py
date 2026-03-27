from pathlib import Path
import xml.etree.ElementTree as ET

from doc_translation_tool.config import AppSettings, LLMSettings
from doc_translation_tool.document_types import DITA_DOCUMENT_TYPE, detect_document_type
from doc_translation_tool.documents import DitaDocumentHandler


def _build_settings(tmp_path: Path) -> AppSettings:
    return AppSettings(
        project_root=str(tmp_path),
        llm=LLMSettings(
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="test-model",
        ),
    )


def test_dita_document_type_is_internal_only_for_now() -> None:
    assert DITA_DOCUMENT_TYPE == "dita"
    assert detect_document_type("topic.dita") == DITA_DOCUMENT_TYPE


def test_dita_handler_extracts_supported_text_nodes(tmp_path: Path) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<topic id='demo'>"
        "<title>相机驱动指南</title>"
        "<shortdesc>用于测试。</shortdesc>"
        "<body>"
        "<p>第一段。</p>"
        "<ul><li>项目一</li><li>项目二</li></ul>"
        "<table><tgroup cols='1'><tbody><row><entry>表格项</entry></row></tbody></tgroup></table>"
        "</body>"
        "</topic>\n"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )

    assert prepared.document_type == DITA_DOCUMENT_TYPE
    assert [segment.text for segment in prepared.segments] == [
        "相机驱动指南",
        "用于测试。",
        "第一段。",
        "项目一",
        "项目二",
        "表格项",
    ]


def test_dita_handler_skips_non_translatable_code_and_attributes(tmp_path: Path) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<topic id='demo'>"
        "<title>标题</title>"
        "<body>"
        "<p>请查看<xref href='docs/guide.dita'>用户指南</xref>继续。</p>"
        "<codeblock>echo hello</codeblock>"
        "<p translate='no'>这段不要翻</p>"
        "</body>"
        "</topic>"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )

    assert [segment.text for segment in prepared.segments] == [
        "标题",
        "请查看",
        "用户指南",
        "继续。",
    ]


def test_dita_handler_rebuilds_translated_text_without_touching_attributes(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<topic id='demo'>"
        "<title>标题</title>"
        "<body>"
        "<p>请查看<xref href='docs/guide.dita'>用户指南</xref>继续。</p>"
        "</body>"
        "</topic>\n"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )
    translated_segment_texts = {
        prepared.segments[0].id: "Title",
        prepared.segments[1].id: "Please see ",
        prepared.segments[2].id: "User Guide",
        prepared.segments[3].id: " for details.",
    }

    rebuilt = handler.rebuild_document(prepared, translated_segment_texts)
    root = ET.fromstring(rebuilt)
    xref = root.find(".//xref")

    assert root.findtext("title") == "Title"
    assert root.find(".//p").text == "Please see "
    assert xref is not None
    assert xref.text == "User Guide"
    assert xref.tail == " for details."
    assert xref.attrib["href"] == "docs/guide.dita"
    assert rebuilt.endswith("\n")


def test_dita_handler_uses_dita_output_extension() -> None:
    handler = DitaDocumentHandler()

    assert handler.output_extension("topic.dita") == ".dita"


def test_dita_handler_protects_technical_literals_and_restores_them(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<topic id='demo'>"
        "<body>"
        "<p>参数 CONFIG_SPINOR_LOGICAL_OFFSET 需要和 /opt/images/boot0.bin 保持一致。</p>"
        "</body>"
        "</topic>\n"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )

    assert prepared.segments[0].text.count("@@PROTECT_") == 2
    rebuilt = handler.rebuild_document(prepared)

    assert "CONFIG_SPINOR_LOGICAL_OFFSET" in rebuilt
    assert "/opt/images/boot0.bin" in rebuilt


def test_dita_handler_splits_long_text_by_sentence_and_rebuilds(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler(max_segment_length=18)
    source_text = (
        "<topic id=\"demo\">"
        "<body>"
        "<p>第一句比较短。第二句也比较短。第三句继续说明。</p>"
        "</body>"
        "</topic>\n"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )

    assert len(prepared.blocks) == 1
    assert len(prepared.blocks[0].segment_ids) >= 2
    assert "".join(segment.text for segment in prepared.segments) == prepared.blocks[0].protected_text
    assert handler.rebuild_document(prepared) == source_text


def test_dita_handler_extracts_note_and_step_content(tmp_path: Path) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<task id='demo'>"
        "<title>步骤说明</title>"
        "<taskbody>"
        "<steps><step><cmd>点击设置。</cmd><stepresult>界面会刷新。</stepresult></step></steps>"
        "<note>请先确认 boot0.bin 已存在。</note>"
        "</taskbody>"
        "</task>"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )

    assert [segment.text for segment in prepared.segments] == [
        "步骤说明",
        "点击设置。",
        "界面会刷新。",
        "请先确认 @@PROTECT_0000@@ 已存在。",
    ]


def test_dita_handler_extracts_section_content_and_skips_screen_block(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<task id='demo'>"
        "<taskbody>"
        "<section><title>准备阶段</title><p>请检查 CONFIG_BOOT_ORDER 和 settings.yaml。</p></section>"
        "<screen>CONFIG_BOOT_ORDER=1</screen>"
        "</taskbody>"
        "</task>"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )

    assert [segment.text for segment in prepared.segments] == [
        "准备阶段",
        "请检查 @@PROTECT_0001@@ 和 @@PROTECT_0000@@。",
    ]


def test_dita_handler_extracts_common_task_prose_containers(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<task id='demo'>"
        "<title>设备初始化流程</title>"
        "<taskbody>"
        "<context><p>开始前，请确认 firmware.bin 已准备完成。</p></context>"
        "<steps><step><cmd>打开设置页面。</cmd><info>如果配置说明不可用，请联系维护人员。</info>"
        "<stepxmp>界面会提示 CONFIG_DEVICE_READY。</stepxmp></step></steps>"
        "<result><p>系统会生成 result.log。</p></result>"
        "<postreq><p>完成后，请查看 docs/report.dita。</p></postreq>"
        "</taskbody>"
        "</task>"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )

    assert [segment.text for segment in prepared.segments] == [
        "设备初始化流程",
        "开始前，请确认 @@PROTECT_0000@@ 已准备完成。",
        "打开设置页面。",
        "如果配置说明不可用，请联系维护人员。",
        "界面会提示 @@PROTECT_0001@@。",
        "系统会生成 @@PROTECT_0002@@。",
        "完成后，请查看 @@PROTECT_0003@@。",
    ]


def test_dita_handler_preserves_xml_declaration_and_doctype(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE task PUBLIC \"-//OASIS//DTD DITA Task//EN\" \"task.dtd\">\n"
        "<task id=\"demo\"><title>标题</title></task>\n"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )
    rebuilt = handler.rebuild_document(
        prepared,
        {prepared.segments[0].id: "Title"},
    )

    assert prepared.leading_xml_text == (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE task PUBLIC \"-//OASIS//DTD DITA Task//EN\" \"task.dtd\">\n"
    )
    assert rebuilt == (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!DOCTYPE task PUBLIC \"-//OASIS//DTD DITA Task//EN\" \"task.dtd\">\n"
        "<task id=\"demo\"><title>Title</title></task>\n"
    )


def test_dita_handler_preserves_leading_comments_and_processing_instructions(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!-- build:keep -->\n"
        "<?workdir value=\"docs\"?>\n"
        "<!DOCTYPE task PUBLIC \"-//OASIS//DTD DITA Task//EN\" \"task.dtd\">\n"
        "<task id=\"demo\"><title>标题</title></task>\n"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )
    rebuilt = handler.rebuild_document(
        prepared,
        {prepared.segments[0].id: "Title"},
    )

    assert prepared.leading_xml_text == (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!-- build:keep -->\n"
        "<?workdir value=\"docs\"?>\n"
        "<!DOCTYPE task PUBLIC \"-//OASIS//DTD DITA Task//EN\" \"task.dtd\">\n"
    )
    assert rebuilt == (
        "<?xml version=\"1.0\" encoding=\"UTF-8\"?>\n"
        "<!-- build:keep -->\n"
        "<?workdir value=\"docs\"?>\n"
        "<!DOCTYPE task PUBLIC \"-//OASIS//DTD DITA Task//EN\" \"task.dtd\">\n"
        "<task id=\"demo\"><title>Title</title></task>\n"
    )


def test_dita_handler_preserves_internal_comments_and_processing_instructions(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler()
    source_text = (
        "<topic id=\"demo\">"
        "<title>标题</title>"
        "<!-- keep me -->"
        "<?audit step=\"after-title\"?>"
        "<body><p>内容</p></body>"
        "</topic>\n"
    )

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )
    rebuilt = handler.rebuild_document(
        prepared,
        {
            prepared.segments[0].id: "Title",
            prepared.segments[1].id: "Content",
        },
    )

    assert "<!-- keep me -->" in rebuilt
    assert "<?audit step=\"after-title\"?>" in rebuilt
    assert "<title>Title</title>" in rebuilt
    assert "<p>Content</p>" in rebuilt
    assert rebuilt.endswith("\n")
