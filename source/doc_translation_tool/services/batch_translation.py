from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Callable

from doc_translation_tool.document_types import is_supported_document
from doc_translation_tool.models import (
    BatchTranslationTask,
    MultiFileTranslationTask,
    TranslationTask,
)
from doc_translation_tool.services.lang_detect import detect_language_for_document
from doc_translation_tool.services.pipeline import (
    DocumentTranslationPipeline,
    TranslationPipelineError,
    TranslationPipelineResult,
)
from doc_translation_tool.utils.logger import PipelineLogger, ProgressReporter


@dataclass(slots=True)
class BatchTranslationFailure:
    """Single-file failure captured during a batch translation run."""

    source_path: str
    stage: str
    message: str


@dataclass(slots=True)
class BatchTranslationPlanItem:
    """Resolved execution item for one source file in a batch run."""

    source_path: str
    resolved_direction: str
    detected_language: str
    detection_confident: bool
    uses_fallback_direction: bool


@dataclass(slots=True)
class BatchTranslationPlan:
    """Execution plan for a directory batch before translation starts."""

    source_dir: str
    output_dir: str
    fallback_direction: str
    items: list[BatchTranslationPlanItem]
    skipped_paths: list[str] = field(default_factory=list)
    skipped_generated_output_paths: list[str] = field(default_factory=list)

    @property
    def total_files(self) -> int:
        return len(self.items)

    @property
    def detected_zh_files(self) -> int:
        return sum(1 for item in self.items if item.detected_language == "zh")

    @property
    def detected_en_files(self) -> int:
        return sum(1 for item in self.items if item.detected_language == "en")

    @property
    def fallback_files(self) -> int:
        return sum(1 for item in self.items if item.uses_fallback_direction)

    @property
    def skipped_generated_files(self) -> int:
        return len(self.skipped_generated_output_paths)


@dataclass(slots=True)
class BatchTranslationResult:
    """Aggregated outcome of a directory-based batch translation run."""

    total_files: int
    successful_files: int
    failed_files: int
    skipped_files: int
    successful_results: list[TranslationPipelineResult] = field(default_factory=list)
    failures: list[BatchTranslationFailure] = field(default_factory=list)
    skipped_paths: list[str] = field(default_factory=list)
    skipped_generated_output_paths: list[str] = field(default_factory=list)
    overall_elapsed_seconds: float = 0.0


class BatchTranslationError(RuntimeError):
    """Fatal error raised before the batch run can begin safely."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


class BatchTranslationService:
    """Execute existing single-file translations sequentially for a file set."""

    def __init__(
        self,
        *,
        pipeline_factory: Callable[[], DocumentTranslationPipeline],
    ) -> None:
        self.pipeline_factory = pipeline_factory

    def scan_source_directory(
        self,
        source_dir: str | Path,
        *,
        recursive: bool = False,
    ) -> tuple[list[Path], list[Path]]:
        root = Path(source_dir).expanduser()
        if not root.exists():
            raise BatchTranslationError("scan_source", "批量翻译源目录不存在")
        if not root.is_dir():
            raise BatchTranslationError("scan_source", "批量翻译源路径必须为文件夹路径")

        iterator = root.rglob("*") if recursive else root.iterdir()
        supported: list[Path] = []
        skipped: list[Path] = []
        for candidate in iterator:
            if not candidate.is_file():
                continue
            if is_supported_document(candidate):
                supported.append(candidate)
            else:
                skipped.append(candidate)

        supported.sort(key=lambda path: path.name.lower())
        skipped.sort(key=lambda path: path.name.lower())
        return supported, skipped

    def build_execution_plan(self, task: BatchTranslationTask) -> BatchTranslationPlan:
        source_files, skipped_paths = self.scan_source_directory(
            task.source_dir,
            recursive=task.recursive,
        )
        if not source_files:
            raise BatchTranslationError(
                "scan_source",
                "未在源目录中找到支持的文档文件（.md 或 .dita）",
            )
        source_files, skipped_generated_output_paths = self._split_generated_output_files(
            source_files
        )
        if not source_files:
            raise BatchTranslationError(
                "scan_source",
                "源目录中的支持文件都被识别为已生成输出文件，没有可翻译的原始文档",
            )

        return BatchTranslationPlan(
            source_dir=task.source_dir,
            output_dir=task.output_dir,
            fallback_direction=task.direction,
            items=[
                self._build_plan_item(path, fallback_direction=task.direction)
                for path in source_files
            ],
            skipped_paths=[str(path) for path in skipped_paths],
            skipped_generated_output_paths=[
                str(path) for path in skipped_generated_output_paths
            ],
        )

    def execute(
        self,
        task: BatchTranslationTask,
        *,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int], None] | None = None,
        on_file_started: Callable[[int, int, str], None] | None = None,
        on_file_succeeded: Callable[[int, int, TranslationPipelineResult], None] | None = None,
        on_file_failed: Callable[[int, int, BatchTranslationFailure], None] | None = None,
    ) -> BatchTranslationResult:
        logger = PipelineLogger(on_log)
        plan = self.build_execution_plan(task)
        logger.batch(
            "自动识别："
            f"中文 {plan.detected_zh_files}，"
            f"英文 {plan.detected_en_files}，"
            f"未确定 {plan.fallback_files}"
        )

        return self._execute_plan_items(
            plan.items,
            output_dir=task.output_dir,
            on_log=on_log,
            on_progress=on_progress,
            on_file_started=on_file_started,
            on_file_succeeded=on_file_succeeded,
            on_file_failed=on_file_failed,
            skipped_paths=plan.skipped_paths,
            skipped_generated_output_paths=plan.skipped_generated_output_paths,
            source_label=task.source_dir,
        )

    def execute_selected_files(
        self,
        task: MultiFileTranslationTask,
        *,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int], None] | None = None,
        on_file_started: Callable[[int, int, str], None] | None = None,
        on_file_succeeded: Callable[[int, int, TranslationPipelineResult], None] | None = None,
        on_file_failed: Callable[[int, int, BatchTranslationFailure], None] | None = None,
        skipped_paths: list[str] | None = None,
        source_label: str | None = None,
    ) -> BatchTranslationResult:
        source_files = [Path(path).expanduser() for path in task.source_paths]
        if not source_files:
            raise BatchTranslationError(
                "scan_source",
                "未在选择列表中找到支持的文档文件（.md 或 .dita）",
            )

        return self._execute_plan_items(
            [
                BatchTranslationPlanItem(
                    source_path=str(path),
                    resolved_direction=task.direction,
                    detected_language="",
                    detection_confident=False,
                    uses_fallback_direction=True,
                )
                for path in source_files
            ],
            output_dir=task.output_dir,
            on_log=on_log,
            on_progress=on_progress,
            on_file_started=on_file_started,
            on_file_succeeded=on_file_succeeded,
            on_file_failed=on_file_failed,
            skipped_paths=skipped_paths or [],
            skipped_generated_output_paths=[],
            source_label=source_label or f"已选择 {len(source_files)} 个文件",
        )

    def _split_generated_output_files(
        self,
        source_files: list[Path],
    ) -> tuple[list[Path], list[Path]]:
        generated_outputs: list[Path] = []
        originals: list[Path] = []
        source_lookup = {path.resolve(strict=False): path for path in source_files}

        for candidate in source_files:
            original_source = self._infer_original_source_path(
                candidate,
                source_lookup=source_lookup,
            )
            if original_source is not None:
                generated_outputs.append(candidate)
                continue
            originals.append(candidate)

        return originals, generated_outputs

    def _infer_original_source_path(
        self,
        candidate: Path,
        *,
        source_lookup: dict[Path, Path],
    ) -> Path | None:
        stem = candidate.stem
        if stem.endswith("_en"):
            base_stem = stem[:-3]
        elif stem.endswith("_zh"):
            base_stem = stem[:-3]
        else:
            return None
        if not base_stem:
            return None

        original_candidate = candidate.with_name(f"{base_stem}{candidate.suffix}")
        return source_lookup.get(original_candidate.resolve(strict=False))

    def _build_plan_item(
        self,
        source_path: str | Path,
        *,
        fallback_direction: str,
    ) -> BatchTranslationPlanItem:
        detection_result = detect_language_for_document(source_path)
        if detection_result.is_confident:
            resolved_direction = (
                "zh_to_en" if detection_result.language == "zh" else "en_to_zh"
            )
            return BatchTranslationPlanItem(
                source_path=str(Path(source_path).expanduser()),
                resolved_direction=resolved_direction,
                detected_language=detection_result.language,
                detection_confident=True,
                uses_fallback_direction=False,
            )

        return BatchTranslationPlanItem(
            source_path=str(Path(source_path).expanduser()),
            resolved_direction=fallback_direction,
            detected_language=detection_result.language,
            detection_confident=False,
            uses_fallback_direction=True,
        )

    def _execute_plan_items(
        self,
        items: list[BatchTranslationPlanItem],
        *,
        output_dir: str,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int], None] | None = None,
        on_file_started: Callable[[int, int, str], None] | None = None,
        on_file_succeeded: Callable[[int, int, TranslationPipelineResult], None] | None = None,
        on_file_failed: Callable[[int, int, BatchTranslationFailure], None] | None = None,
        skipped_paths: list[str] | None = None,
        skipped_generated_output_paths: list[str] | None = None,
        source_label: str | None = None,
    ) -> BatchTranslationResult:
        logger = PipelineLogger(on_log)
        progress = ProgressReporter(on_progress)

        skipped_paths = skipped_paths or []
        skipped_generated_output_paths = skipped_generated_output_paths or []
        source_label = source_label or f"已选择 {len(items)} 个文件"
        started_at = perf_counter()
        logger.batch(f"来源：{source_label}")
        logger.batch(f"待翻译文件数：{len(items)}")
        progress.report(f"开始批量翻译：共 {len(items)} 个文件", 0)
        if skipped_paths:
            logger.batch(f"已跳过不支持文件：{len(skipped_paths)}")
        if skipped_generated_output_paths:
            logger.batch(
                f"已自动跳过疑似已生成输出文件：{len(skipped_generated_output_paths)}"
            )

        successful_results: list[TranslationPipelineResult] = []
        failures: list[BatchTranslationFailure] = []
        total_files = len(items)
        progress_span = 100
        pipeline = self.pipeline_factory()
        runtime_session_factory = getattr(pipeline, "create_runtime_session", None)
        runtime_session = runtime_session_factory() if callable(runtime_session_factory) else None

        try:
            for index, item in enumerate(items, start=1):
                source_path = Path(item.source_path).expanduser()
                progress_percent = max(0, int(((index - 1) / total_files) * progress_span))
                display_name = source_path.name
                progress.report(
                    f"正在翻译：第 {index}/{total_files} 个文件：{display_name}",
                    progress_percent,
                )
                logger.batch(
                    f"开始文件 {index}/{total_files}：{source_path}；方向：{item.resolved_direction}"
                )
                if on_file_started is not None:
                    on_file_started(index, total_files, str(source_path))

                try:
                    result = pipeline.execute(
                        TranslationTask(
                            source_path=str(source_path),
                            output_dir=output_dir,
                            direction=item.resolved_direction,
                        ),
                        on_log=on_log,
                        runtime_session=runtime_session,
                    )
                except TranslationPipelineError as exc:
                    failure = BatchTranslationFailure(
                        source_path=str(source_path),
                        stage=exc.stage,
                        message=exc.message,
                    )
                    failures.append(failure)
                    logger.batch(
                        f"文件失败 {index}/{total_files}：{source_path}；阶段：{exc.stage}；原因：{exc.message}"
                    )
                    if on_file_failed is not None:
                        on_file_failed(index, total_files, failure)
                    continue

                successful_results.append(result)
                logger.batch(f"文件完成 {index}/{total_files}：{result.output_path}")
                if on_file_succeeded is not None:
                    on_file_succeeded(index, total_files, result)
        finally:
            if runtime_session is not None:
                runtime_session.close()

        overall_elapsed_seconds = perf_counter() - started_at
        progress.report("批量翻译完成", 100)
        logger.batch(
            f"完成："
            f"成功 {len(successful_results)}，"
            f"失败 {len(failures)}，"
            f"跳过 {len(skipped_paths) + len(skipped_generated_output_paths)}，"
            f"总耗时 {overall_elapsed_seconds:.2f}s"
        )
        return BatchTranslationResult(
            total_files=total_files,
            successful_files=len(successful_results),
            failed_files=len(failures),
            skipped_files=len(skipped_paths) + len(skipped_generated_output_paths),
            successful_results=successful_results,
            failures=failures,
            skipped_paths=list(skipped_paths),
            skipped_generated_output_paths=list(skipped_generated_output_paths),
            overall_elapsed_seconds=overall_elapsed_seconds,
        )
