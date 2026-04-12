from __future__ import annotations

from pathlib import Path

import pytest

from doc_translation_tool.models import BatchTranslationTask, MultiFileTranslationTask
from doc_translation_tool.services.batch_translation import (
    BatchTranslationError,
    BatchTranslationPlan,
    BatchTranslationService,
)
from doc_translation_tool.services.pipeline import (
    TranslationPipelineError,
    TranslationPipelineResult,
)


class FakeRuntimeSession:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class FakeDocumentTranslationPipeline:
    def __init__(self, *, failures: dict[str, tuple[str, str]] | None = None) -> None:
        self.failures = failures or {}
        self.calls: list[tuple[str, str, str]] = []
        self.runtime_sessions_seen: list[FakeRuntimeSession | None] = []
        self.created_runtime_session = FakeRuntimeSession()
        self.create_runtime_session_calls = 0

    def create_runtime_session(self) -> FakeRuntimeSession:
        self.create_runtime_session_calls += 1
        return self.created_runtime_session

    def execute(
        self,
        task,
        *,
        on_log=None,
        on_progress=None,
        on_connection_checked=None,
        runtime_session=None,
    ):
        del on_progress, on_connection_checked
        self.calls.append((task.source_path, task.output_dir, task.direction))
        self.runtime_sessions_seen.append(runtime_session)
        if on_log is not None:
            on_log(f"[单文件] {Path(task.source_path).name}")

        file_name = Path(task.source_path).name
        failure = self.failures.get(file_name)
        if failure is not None:
            stage, message = failure
            raise TranslationPipelineError(stage, message)

        output_name = f"{Path(task.source_path).stem}_{'en' if task.direction == 'zh_to_en' else 'zh'}{Path(task.source_path).suffix}"
        return TranslationPipelineResult(
            output_path=str(Path(task.output_dir) / output_name),
            final_markdown_text="translated",
            connection_message="OK",
            total_segments=1,
            total_batches=1,
            overall_elapsed_seconds=0.1,
        )


def test_batch_translation_service_scans_only_supported_files(tmp_path: Path) -> None:
    (tmp_path / "a.md").write_text("# a\n", encoding="utf-8")
    (tmp_path / "b.dita").write_text("<topic id='b'><title>B</title></topic>\n", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("skip\n", encoding="utf-8")

    service = BatchTranslationService(
        pipeline_factory=lambda: FakeDocumentTranslationPipeline(),
    )

    supported, skipped = service.scan_source_directory(tmp_path)

    assert [path.name for path in supported] == ["a.md", "b.dita"]
    assert [path.name for path in skipped] == ["notes.txt"]


def test_batch_translation_service_executes_files_sequentially_and_collects_results(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "a.md").write_text("# a\n", encoding="utf-8")
    (source_dir / "b.dita").write_text("<topic id='b'><title>B</title></topic>\n", encoding="utf-8")
    (source_dir / "skip.txt").write_text("skip\n", encoding="utf-8")

    pipelines: list[FakeDocumentTranslationPipeline] = []

    def build_pipeline() -> FakeDocumentTranslationPipeline:
        pipeline = FakeDocumentTranslationPipeline()
        pipelines.append(pipeline)
        return pipeline

    service = BatchTranslationService(pipeline_factory=build_pipeline)
    logs: list[str] = []
    progress: list[tuple[str, int]] = []
    started: list[tuple[int, int, str]] = []
    succeeded: list[tuple[int, int, str]] = []

    result = service.execute(
        BatchTranslationTask(
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            direction="zh_to_en",
        ),
        on_log=logs.append,
        on_progress=lambda message, percent: progress.append((message, percent)),
        on_file_started=lambda index, total, path: started.append((index, total, Path(path).name)),
        on_file_succeeded=lambda index, total, item: succeeded.append((index, total, Path(item.output_path).name)),
    )

    assert result.total_files == 2
    assert result.successful_files == 2
    assert result.failed_files == 0
    assert result.skipped_files == 1
    assert [Path(item.output_path).name for item in result.successful_results] == [
        "a_en.md",
        "b_en.dita",
    ]
    assert started == [
        (1, 2, "a.md"),
        (2, 2, "b.dita"),
    ]
    assert succeeded == [
        (1, 2, "a_en.md"),
        (2, 2, "b_en.dita"),
    ]
    assert progress[-1] == ("批量翻译完成", 100)
    assert len(pipelines) == 1
    assert pipelines[0].create_runtime_session_calls == 1
    assert pipelines[0].calls == [
        (str(source_dir / "a.md"), str(output_dir), "zh_to_en"),
        (str(source_dir / "b.dita"), str(output_dir), "zh_to_en"),
    ]
    assert pipelines[0].runtime_sessions_seen == [
        pipelines[0].created_runtime_session,
        pipelines[0].created_runtime_session,
    ]
    assert pipelines[0].created_runtime_session.closed is True
    assert any("[批量] 待翻译文件数：2" in message for message in logs)


def test_batch_translation_service_executes_selected_files_list(
    tmp_path: Path,
) -> None:
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    source_one = tmp_path / "a.md"
    source_two = tmp_path / "b.dita"
    source_one.write_text("# a\n", encoding="utf-8")
    source_two.write_text("<topic id='b'><title>B</title></topic>\n", encoding="utf-8")

    pipeline = FakeDocumentTranslationPipeline()
    service = BatchTranslationService(pipeline_factory=lambda: pipeline)

    result = service.execute_selected_files(
        MultiFileTranslationTask(
            source_paths=[str(source_one), str(source_two)],
            output_dir=str(output_dir),
            direction="zh_to_en",
        )
    )

    assert result.total_files == 2
    assert result.successful_files == 2
    assert result.failed_files == 0
    assert result.skipped_files == 0
    assert pipeline.calls == [
        (str(source_one), str(output_dir), "zh_to_en"),
        (str(source_two), str(output_dir), "zh_to_en"),
    ]
    assert pipeline.created_runtime_session.closed is True


def test_batch_translation_service_continues_after_single_file_failure(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "a.md").write_text("# a\n", encoding="utf-8")
    (source_dir / "b.md").write_text("# b\n", encoding="utf-8")

    failure_map = {"b.md": ("translate", "mock failure")}
    pipeline = FakeDocumentTranslationPipeline(failures=failure_map)

    service = BatchTranslationService(
        pipeline_factory=lambda: pipeline,
    )
    failed: list[tuple[int, int, str, str]] = []

    result = service.execute(
        BatchTranslationTask(
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            direction="zh_to_en",
        ),
        on_file_failed=lambda index, total, item: failed.append(
            (index, total, Path(item.source_path).name, item.stage)
        ),
    )

    assert result.total_files == 2
    assert result.successful_files == 1
    assert result.failed_files == 1
    assert len(result.failures) == 1
    assert result.failures[0].source_path.endswith("b.md")
    assert result.failures[0].stage == "translate"
    assert failed == [(2, 2, "b.md", "translate")]
    assert pipeline.create_runtime_session_calls == 1
    assert pipeline.runtime_sessions_seen == [
        pipeline.created_runtime_session,
        pipeline.created_runtime_session,
    ]
    assert pipeline.created_runtime_session.closed is True


def test_batch_translation_service_rejects_missing_source_dir(tmp_path: Path) -> None:
    service = BatchTranslationService(
        pipeline_factory=lambda: FakeDocumentTranslationPipeline(),
    )

    with pytest.raises(BatchTranslationError, match="批量翻译源目录不存在") as exc_info:
        service.execute(
            BatchTranslationTask(
                source_dir=str(tmp_path / "missing"),
                output_dir=str(tmp_path),
                direction="zh_to_en",
            )
        )

    assert exc_info.value.stage == "scan_source"


def test_batch_translation_service_rejects_empty_supported_file_set(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "notes.txt").write_text("skip\n", encoding="utf-8")

    service = BatchTranslationService(
        pipeline_factory=lambda: FakeDocumentTranslationPipeline(),
    )

    with pytest.raises(BatchTranslationError, match="未在源目录中找到支持的文档文件") as exc_info:
        service.execute(
            BatchTranslationTask(
                source_dir=str(source_dir),
                output_dir=str(output_dir),
                direction="zh_to_en",
            )
        )

    assert exc_info.value.stage == "scan_source"


def test_batch_translation_service_builds_execution_plan_with_detected_directions(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    zh_file = source_dir / "a_chinese.md"
    en_file = source_dir / "b_english.dita"
    unknown_file = source_dir / "c_neutral.md"
    zh_file.write_text("本文档用于说明相机驱动架构和启动流程。\n", encoding="utf-8")
    en_file.write_text(
        "<topic id='b'><title>Architecture Overview</title><body><p>This document explains the camera driver startup sequence and runtime behavior in detail.</p></body></topic>\n",
        encoding="utf-8",
    )
    unknown_file.write_text("v1.2.3\n", encoding="utf-8")

    service = BatchTranslationService(
        pipeline_factory=lambda: FakeDocumentTranslationPipeline(),
    )

    plan = service.build_execution_plan(
        BatchTranslationTask(
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            direction="zh_to_en",
        )
    )

    assert isinstance(plan, BatchTranslationPlan)
    assert plan.total_files == 3
    assert plan.detected_zh_files == 1
    assert plan.detected_en_files == 1
    assert plan.fallback_files == 1
    assert [
        (Path(item.source_path).name, item.detected_language, item.resolved_direction)
        for item in plan.items
    ] == [
        ("a_chinese.md", "zh", "zh_to_en"),
        ("b_english.dita", "en", "en_to_zh"),
        ("c_neutral.md", "mixed_or_unknown", "zh_to_en"),
    ]


def test_batch_translation_service_executes_directory_files_with_per_file_directions(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "a_chinese.md").write_text(
        "本文档用于说明相机驱动架构和启动流程。\n",
        encoding="utf-8",
    )
    (source_dir / "b_english.md").write_text(
        "This document explains the camera driver startup sequence and runtime behavior in detail.\n",
        encoding="utf-8",
    )
    (source_dir / "c_neutral.md").write_text("v1.2.3\n", encoding="utf-8")

    pipeline = FakeDocumentTranslationPipeline()
    service = BatchTranslationService(pipeline_factory=lambda: pipeline)
    logs: list[str] = []

    result = service.execute(
        BatchTranslationTask(
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            direction="zh_to_en",
        ),
        on_log=logs.append,
    )

    assert result.total_files == 3
    assert result.successful_files == 3
    assert pipeline.calls == [
        (str(source_dir / "a_chinese.md"), str(output_dir), "zh_to_en"),
        (str(source_dir / "b_english.md"), str(output_dir), "en_to_zh"),
        (str(source_dir / "c_neutral.md"), str(output_dir), "zh_to_en"),
    ]
    assert any("[批量] 自动识别：中文 1，英文 1，未确定 1" in message for message in logs)


def test_batch_translation_service_build_execution_plan_skips_generated_outputs(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "guide.md").write_text(
        "本文档用于说明相机驱动架构和启动流程。\n",
        encoding="utf-8",
    )
    (source_dir / "guide_en.md").write_text(
        "This is a previously generated translation.\n",
        encoding="utf-8",
    )
    (source_dir / "notes.txt").write_text("skip\n", encoding="utf-8")

    service = BatchTranslationService(
        pipeline_factory=lambda: FakeDocumentTranslationPipeline(),
    )

    plan = service.build_execution_plan(
        BatchTranslationTask(
            source_dir=str(source_dir),
            output_dir=str(output_dir),
            direction="zh_to_en",
        )
    )

    assert [Path(item.source_path).name for item in plan.items] == ["guide.md"]
    assert [Path(path).name for path in plan.skipped_paths] == ["notes.txt"]
    assert [Path(path).name for path in plan.skipped_generated_output_paths] == [
        "guide_en.md"
    ]
    assert plan.skipped_generated_files == 1


def test_batch_translation_service_execute_skips_generated_outputs_on_rerun(
    tmp_path: Path,
) -> None:
    source_dir = tmp_path / "src"
    source_dir.mkdir()
    (source_dir / "guide.md").write_text(
        "本文档用于说明相机驱动架构和启动流程。\n",
        encoding="utf-8",
    )
    (source_dir / "guide_en.md").write_text(
        "This is a previously generated translation.\n",
        encoding="utf-8",
    )

    pipeline = FakeDocumentTranslationPipeline()
    service = BatchTranslationService(pipeline_factory=lambda: pipeline)
    logs: list[str] = []

    result = service.execute(
        BatchTranslationTask(
            source_dir=str(source_dir),
            output_dir=str(source_dir),
            direction="zh_to_en",
        ),
        on_log=logs.append,
    )

    assert result.total_files == 1
    assert result.successful_files == 1
    assert result.skipped_files == 1
    assert [Path(path).name for path in result.skipped_generated_output_paths] == [
        "guide_en.md"
    ]
    assert pipeline.calls == [
        (str(source_dir / "guide.md"), str(source_dir), "zh_to_en"),
    ]
    assert any("已自动跳过疑似已生成输出文件：1" in message for message in logs)
