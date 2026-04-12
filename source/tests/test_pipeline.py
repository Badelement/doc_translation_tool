from __future__ import annotations

from pathlib import Path
import re

import pytest

from doc_translation_tool.config import AppSettings, LLMSettings
from doc_translation_tool.llm import BaseLLMClient, LLMClientError, TranslationResult
from doc_translation_tool.models import TranslationTask
from doc_translation_tool.services import (
    DocumentTranslationPipeline,
    TranslationPipelineError,
)
from doc_translation_tool.services.translation_cache import TranslationCheckpointCache


class FakePipelineClient(BaseLLMClient):
    def __init__(self, settings: LLMSettings, *, fail_connection: bool = False) -> None:
        super().__init__(settings)
        self.fail_connection = fail_connection
        self.closed = False
        self.close_calls = 0
        self.check_connection_calls = 0
        self.glossary_calls: list[list[dict[str, str]] | None] = []

    def check_connection(self) -> str:
        self.check_connection_calls += 1
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
                .replace("相机驱动指南", "Camera Driver Guide")
                .replace("用户指南", "User Guide")
                .replace("使用", "Use ")
                .replace("查看", "see ")
                .replace("文档", "docs")
                .replace("张三", "John Zhang")
            )
            if direction == "zh_to_en":
                translated_text = re.sub(
                    r"[\u4e00-\u9fff]+",
                    "translated",
                    translated_text,
                )
                translated_text = translated_text.replace("，", ", ").replace("。", ".")
            else:
                translated_text = re.sub(
                    r"\b[A-Za-z][A-Za-z0-9_-]*\b",
                    "已翻译",
                    translated_text,
                )
            translated_items.append(
                TranslationResult(id=item.id, translated_text=translated_text)
            )
        return translated_items

    def close(self) -> None:
        self.close_calls += 1
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
    assert result.reused_cached_segments == 0
    assert result.rate_limit_backoff_count == 0
    assert result.split_batch_fallback_count == 0
    assert result.single_segment_placeholder_fallback_count == 0
    assert result.overall_elapsed_seconds >= 0
    assert progress_events[0][1] == 0
    assert ("翻译中：已完成批次 0/1", 45) in progress_events
    assert ("翻译中：正在处理第 1/1 批", 46) in progress_events
    assert any(message.startswith("翻译中：已完成批次 ") for message, _percent in progress_events)
    assert ("正在写入输出文件", 97) in progress_events
    assert progress_events[-1] == ("翻译完成", 100)
    assert any("片段总数" in message for message in logs)
    assert any("[stats]" in message for message in logs)
    assert client.glossary_calls == [[]]
    assert client.closed is True


def test_pipeline_runtime_session_reuses_client_and_connection_check(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_one = tmp_path / "guide_a.md"
    source_two = tmp_path / "guide_b.md"
    source_one.write_text("这是一个测试。\n", encoding="utf-8")
    source_two.write_text("这是一个测试。\n", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()

    client = FakePipelineClient(_build_settings(project_root).llm)
    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
    )
    runtime_session = pipeline.create_runtime_session()

    try:
        first_result = pipeline.execute(
            TranslationTask(
                source_path=str(source_one),
                output_dir=str(output_dir),
                direction="zh_to_en",
            ),
            runtime_session=runtime_session,
        )
        second_result = pipeline.execute(
            TranslationTask(
                source_path=str(source_two),
                output_dir=str(output_dir),
                direction="zh_to_en",
            ),
            runtime_session=runtime_session,
        )
    finally:
        runtime_session.close()

    assert Path(first_result.output_path).name == "guide_a_en.md"
    assert Path(second_result.output_path).name == "guide_b_en.md"
    assert client.check_connection_calls == 1
    assert client.close_calls == 1
    assert client.closed is True
    assert client.glossary_calls == [[], []]


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


def test_pipeline_ignores_corrupt_checkpoint_cache_and_clears_it(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "guide.md"
    source_file.write_text("杩欐槸涓€涓祴璇曘€俓n", encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    client = FakePipelineClient(_build_settings(project_root).llm)
    checkpoint_cache = TranslationCheckpointCache()
    cache_path = checkpoint_cache.build_cache_path(
        source_path=source_file,
        output_dir=output_dir,
        direction="zh_to_en",
    )
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("{bad json", encoding="utf-8")

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
        checkpoint_cache=checkpoint_cache,
    )

    result = pipeline.execute(
        TranslationTask(
            source_path=str(source_file),
            output_dir=str(output_dir),
            direction="zh_to_en",
        )
    )

    assert Path(result.output_path).exists() is True
    assert cache_path.exists() is False
    assert cache_path.parent.exists() is False
    assert client.closed is True


def test_pipeline_wraps_dita_parse_failure_with_stage(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "topic.dita"
    source_file.write_text("<topic><title>broken</title>", encoding="utf-8")
    client = FakePipelineClient(_build_settings(project_root).llm)

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
    )

    with pytest.raises(TranslationPipelineError, match="文档解析失败") as exc_info:
        pipeline.execute(
            TranslationTask(
                source_path=str(source_file),
                output_dir=str(tmp_path),
                direction="zh_to_en",
            )
        )

    assert exc_info.value.stage == "parse_document"
    assert client.closed is True


def test_pipeline_surfaces_document_handler_error_without_name_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "guide.md"
    source_file.write_text("这是一个测试。\n", encoding="utf-8")
    client = FakePipelineClient(_build_settings(project_root).llm)

    pipeline = DocumentTranslationPipeline(
        project_root=project_root,
        settings_loader=lambda _root: _build_settings(project_root),
        client_factory=lambda _settings: client,
    )
    monkeypatch.setattr(pipeline, "_resolve_document_handler", lambda _path: None)

    with pytest.raises(
        TranslationPipelineError,
        match=r"未找到文件扩展名 '\.md' 对应的文档处理器",
    ) as exc_info:
        pipeline.execute(
            TranslationTask(
                source_path=str(source_file),
                output_dir=str(tmp_path),
                direction="zh_to_en",
            )
        )

    assert exc_info.value.stage == "document_handler"
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
    assert any("[解析] 文档块总数：" in message for message in logs)
    assert any("[翻译] 总批次数：" in message for message in logs)
    assert any("[重试] 批次 1/" in message for message in logs)
    assert any("耗时" in message for message in logs)


def test_pipeline_detects_dita_by_default_and_writes_dita_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "topic.dita"
    source_file.write_text(
        (
            "<topic id='demo'>"
            "<title>相机驱动指南</title>"
            "<body><p>请查看<xref href='docs/guide.dita'>用户指南</xref>继续。</p></body>"
            "</topic>\n"
        ),
        encoding="utf-8",
    )
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    logs: list[str] = []
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
    )

    output_text = Path(result.output_path).read_text(encoding="utf-8")

    assert Path(result.output_path) == output_dir / "topic_en.dita"
    assert "<title>相机驱动指南</title>" not in output_text
    assert 'href="docs/guide.dita"' in output_text
    assert any("[文档] 类型：dita" in message for message in logs)
