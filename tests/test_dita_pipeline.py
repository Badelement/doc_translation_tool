from __future__ import annotations

from pathlib import Path

from doc_translation_tool.config import AppSettings, LLMSettings
from doc_translation_tool.document_types import DITA_DOCUMENT_TYPE
from doc_translation_tool.llm import BaseLLMClient, LLMClientError, TranslationResult
from doc_translation_tool.models import TranslationTask
from doc_translation_tool.services import DocumentTranslationPipeline


class FakeDitaPipelineClient(BaseLLMClient):
    def __init__(self, settings: LLMSettings) -> None:
        super().__init__(settings)
        self.closed = False

    def check_connection(self) -> str:
        return "OK"

    def translate_batch(self, items, direction: str, glossary=None):
        del direction, glossary
        translated_items: list[TranslationResult] = []
        for item in items:
            translated_text = (
                item.text
                .replace("相机驱动指南", "Camera Driver Guide")
                .replace("用于测试。", "Used for testing.")
                .replace("请查看", "Please see ")
                .replace("用户指南", "User Guide")
                .replace("继续。", " for details.")
            )
            translated_items.append(
                TranslationResult(id=item.id, translated_text=translated_text)
            )
        return translated_items

    def close(self) -> None:
        self.closed = True


def _build_settings(project_root: Path) -> AppSettings:
    return AppSettings(
        project_root=str(project_root),
        llm=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret-key",
            model="test-model",
            batch_size=2,
            max_retries=1,
        ),
    )


def test_pipeline_executes_internal_dita_flow_when_detector_is_overridden(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "topic.dita"
    source_file.write_text(
        (
            "<topic id='demo'>"
            "<title>相机驱动指南</title>"
            "<shortdesc>用于测试。</shortdesc>"
            "<body>"
            "<p>请查看<xref href='docs/guide.dita'>用户指南</xref>继续。</p>"
            "</body>"
            "</topic>\n"
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    logs: list[str] = []
    progress_events: list[tuple[str, int]] = []
    client = FakeDitaPipelineClient(_build_settings(project_root).llm)
    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
        document_type_detector=lambda _path: DITA_DOCUMENT_TYPE,
    )

    result = pipeline.execute(
        TranslationTask(
            source_path=str(source_file),
            output_dir=str(output_dir),
            direction="zh_to_en",
        ),
        on_log=logs.append,
        on_progress=lambda message, percent: progress_events.append((message, percent)),
    )

    output_path = Path(result.output_path)
    output_text = output_path.read_text(encoding="utf-8")

    assert output_path == output_dir / "topic_en.dita"
    assert "<title>Camera Driver Guide</title>" in output_text
    assert "<shortdesc>Used for testing.</shortdesc>" in output_text
    assert "<p>Please see <xref href=\"docs/guide.dita\">User Guide</xref> for details.</p>" in output_text
    assert result.connection_message == "OK"
    assert result.total_segments == 5
    assert any("[文档] 类型：dita" in message for message in logs)
    assert ("正在写入输出文件", 97) in progress_events
    assert progress_events[-1] == ("翻译完成", 100)
    assert client.closed is True


def test_pipeline_internal_dita_flow_clears_checkpoint_after_success(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "topic.dita"
    source_file.write_text(
        "<topic id='demo'><title>相机驱动指南</title></topic>\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    client = FakeDitaPipelineClient(_build_settings(project_root).llm)
    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
        document_type_detector=lambda _path: DITA_DOCUMENT_TYPE,
    )

    first_result = pipeline.execute(
        TranslationTask(
            source_path=str(source_file),
            output_dir=str(output_dir),
            direction="zh_to_en",
        )
    )

    assert Path(first_result.output_path).name == "topic_en.dita"
    cache_dir = output_dir / ".doc_translation_cache"
    assert not cache_dir.exists() or list(cache_dir.iterdir()) == []
