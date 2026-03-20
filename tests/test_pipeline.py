from __future__ import annotations

from pathlib import Path

import pytest

from doc_translation_tool.config import AppSettings, LLMSettings
from doc_translation_tool.llm import BaseLLMClient, LLMClientError, TranslationResult
from doc_translation_tool.models import TranslationTask
from doc_translation_tool.services import (
    DocumentTranslationPipeline,
    TranslationPipelineError,
)


class FakePipelineClient(BaseLLMClient):
    def __init__(self, settings: LLMSettings, *, fail_connection: bool = False) -> None:
        super().__init__(settings)
        self.fail_connection = fail_connection
        self.closed = False
        self.glossary_calls: list[list[dict[str, str]] | None] = []

    def check_connection(self) -> str:
        if self.fail_connection:
            raise LLMClientError("connection refused")
        return "OK"

    def translate_batch(self, items, direction: str, glossary=None):
        self.glossary_calls.append(glossary)
        translated_items: list[TranslationResult] = []
        for item in items:
            translated_text = (
                item.text
                .replace("这是一个测试。", "This is a test.")
                .replace("使用", "Use ")
                .replace("查看", "see ")
                .replace("文档", "docs")
                .replace("张三", "John Zhang")
            )
            translated_items.append(
                TranslationResult(id=item.id, translated_text=translated_text)
            )
        return translated_items

    def close(self) -> None:
        self.closed = True


def _build_settings(
    project_root: Path,
    *,
    front_matter_translatable_fields: tuple[str, ...] = ("title", "subtitle", "desc"),
) -> AppSettings:
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
        front_matter_translatable_fields=front_matter_translatable_fields,
    )


def test_pipeline_executes_full_flow_and_writes_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "guide.md"
    source_file.write_text("这是一个测试。\n", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    logs: list[str] = []
    progress_events: list[tuple[str, int]] = []
    client = FakePipelineClient(_build_settings(project_root).llm)

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
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

    assert output_path == output_dir / "guide_en.md"
    assert output_path.read_text(encoding="utf-8") == "This is a test.\n"
    assert result.connection_message == "OK"
    assert result.total_segments == 1
    assert result.retry_attempts == 0
    assert progress_events[0][1] == 0
    assert ("正在等待首批结果", 50) in progress_events
    assert any(message.startswith("已完成批次 ") for message, _percent in progress_events)
    assert progress_events[-1] == ("翻译完成", 100)
    assert any("片段总数" in message for message in logs)
    assert client.glossary_calls == [[]]
    assert client.closed is True


def test_pipeline_wraps_connection_failure_with_stage(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "guide.md"
    source_file.write_text("这是一个测试。\n", encoding="utf-8")
    client = FakePipelineClient(_build_settings(project_root).llm, fail_connection=True)

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
    )

    with pytest.raises(TranslationPipelineError, match="模型连接失败"):
        pipeline.execute(
            TranslationTask(
                source_path=str(source_file),
                output_dir=str(tmp_path),
                direction="zh_to_en",
            )
        )

    assert client.closed is True


def test_pipeline_wraps_model_config_failure_without_masking_original_stage(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "guide.md"
    source_file.write_text("这是一个测试。\n", encoding="utf-8")

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: (_ for _ in ()).throw(ValueError("missing base_url")),
    )

    with pytest.raises(TranslationPipelineError, match="模型配置无效：missing base_url") as exc_info:
        pipeline.execute(
            TranslationTask(
                source_path=str(source_file),
                output_dir=str(tmp_path),
                direction="zh_to_en",
            )
        )

    assert exc_info.value.stage == "model_config"


def test_pipeline_loads_glossary_and_passes_it_to_client(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    (project_root / "glossary.json").write_text(
        '[{"source": "远程处理音效", "target": "remote sound effect"}]\n',
        encoding="utf-8",
    )
    source_file = tmp_path / "guide.md"
    source_file.write_text("杩欐槸涓€涓祴璇曘€俓n", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    client = FakePipelineClient(_build_settings(project_root).llm)

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
    )

    pipeline.execute(
        TranslationTask(
            source_path=str(source_file),
            output_dir=str(output_dir),
            direction="zh_to_en",
        )
    )

    assert client.glossary_calls == [
        [{"source": "远程处理音效", "target": "remote sound effect"}]
    ]


def test_pipeline_wraps_glossary_load_failure_with_stage(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "guide.md"
    source_file.write_text("杩欐槸涓€涓祴璇曘€俓n", encoding="utf-8")
    client = FakePipelineClient(_build_settings(project_root).llm)

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
        glossary_loader=lambda _path: (_ for _ in ()).throw(ValueError("bad glossary")),
    )

    with pytest.raises(TranslationPipelineError, match="术语表加载失败"):
        pipeline.execute(
            TranslationTask(
                source_path=str(source_file),
                output_dir=str(tmp_path),
                direction="zh_to_en",
            )
        )

    assert client.closed is True


def test_pipeline_uses_front_matter_fields_from_settings_for_default_protector(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "guide.md"
    source_file.write_text(
        "---\n"
        "author: 张三\n"
        "---\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    client = FakePipelineClient(
        _build_settings(
            project_root,
            front_matter_translatable_fields=("author",),
        ).llm
    )

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(
            project_root,
            front_matter_translatable_fields=("author",),
        ),
        client_factory=lambda _settings: client,
    )

    result = pipeline.execute(
        TranslationTask(
            source_path=str(source_file),
            output_dir=str(output_dir),
            direction="zh_to_en",
        )
    )

    assert Path(result.output_path).read_text(encoding="utf-8") == (
        "---\n"
        "author: John Zhang\n"
        "---\n"
    )


def test_pipeline_emits_detailed_translation_logs_for_retries(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "guide.md"
    source_file.write_text(
        "第一句比较短。第二句也比较短。第三句继续说明。第四句补充细节。\n",
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    logs: list[str] = []

    class RetryPipelineClient(FakePipelineClient):
        def __init__(self, settings: LLMSettings) -> None:
            super().__init__(settings)
            self._failed_once = False

        def translate_batch(self, items, direction: str, glossary=None):
            if not self._failed_once:
                self._failed_once = True
                raise LLMClientError("temporary batch failure")
            return super().translate_batch(items, direction, glossary)

    client = RetryPipelineClient(
        _build_settings(project_root).llm
    )
    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
    )

    pipeline.execute(
        TranslationTask(
            source_path=str(source_file),
            output_dir=str(output_dir),
            direction="zh_to_en",
        ),
        on_log=logs.append,
    )

    assert any("[配置] 模型：" in message for message in logs)
    assert any("[解析] Markdown 块总数：" in message for message in logs)
    assert any("[翻译] 总批次数：" in message for message in logs)
    assert any("[重试] 批次 1/" in message for message in logs)
    assert any("耗时" in message for message in logs)
