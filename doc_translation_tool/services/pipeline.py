from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable

from doc_translation_tool.config import AppSettings, load_app_settings
from doc_translation_tool.llm import LLMClientError, create_llm_client
from doc_translation_tool.markdown import MarkdownParser, MarkdownProtector, MarkdownSegmenter
from doc_translation_tool.models.schema import TranslationTask
from doc_translation_tool.services.glossary_loader import load_glossary
from doc_translation_tool.services.output_writer import (
    MarkdownOutputWriter,
    OutputWriteError,
    OutputWriteResult,
)
from doc_translation_tool.services.task_service import BatchTranslationResult, TranslationTaskService


@dataclass(slots=True)
class TranslationPipelineResult:
    """Final output of the translation pipeline."""

    output_path: str
    final_markdown_text: str
    connection_message: str
    total_segments: int
    total_batches: int
    retry_attempts: int = 0


class TranslationPipelineError(RuntimeError):
    """Stage-aware pipeline failure that can be surfaced in the GUI."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


class DocumentTranslationPipeline:
    """Run the full Markdown translation flow from input file to output file."""

    def __init__(
        self,
        *,
        project_root: str | Path,
        settings_loader: Callable[[str | Path], AppSettings] = load_app_settings,
        client_factory=create_llm_client,
        parser: MarkdownParser | None = None,
        protector: MarkdownProtector | None = None,
        segmenter: MarkdownSegmenter | None = None,
        output_writer: MarkdownOutputWriter | None = None,
        task_service_factory: Callable[[object], TranslationTaskService] | None = None,
        glossary_loader: Callable[[str | Path], list[dict[str, str]]] = load_glossary,
    ) -> None:
        self.project_root = Path(project_root)
        self.settings_loader = settings_loader
        self.client_factory = client_factory
        self.parser = parser or MarkdownParser()
        self.protector = protector
        self.segmenter = segmenter or MarkdownSegmenter()
        self.output_writer = output_writer or MarkdownOutputWriter()
        self.task_service_factory = task_service_factory or TranslationTaskService
        self.glossary_loader = glossary_loader

    def execute(
        self,
        task: TranslationTask,
        *,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[str, int], None] | None = None,
        on_connection_checked: Callable[[str], None] | None = None,
    ) -> TranslationPipelineResult:
        def emit_log(message: str) -> None:
            if on_log is not None:
                on_log(message)

        def emit_progress(message: str, percent: int) -> None:
            if on_progress is not None:
                on_progress(message, percent)

        def format_elapsed(seconds: float) -> str:
            return f"{seconds:.2f}s"

        overall_started_at = perf_counter()
        emit_progress("准备翻译任务", 0)
        emit_log(f"[文件] 开始读取：{task.source_path}")

        source_read_started_at = perf_counter()
        try:
            source_text = Path(task.source_path).read_text(encoding="utf-8")
        except OSError as exc:
            raise TranslationPipelineError("read_source", f"读取源文件失败：{exc}") from exc

        emit_log(
            f"[文件] 源文件读取完成，耗时 {format_elapsed(perf_counter() - source_read_started_at)}。"
        )
        emit_progress("源文件读取完成", 10)

        client = None
        try:
            settings = self.settings_loader(self.project_root)
            client = self.client_factory(settings.llm)
        except (ValueError, OSError) as exc:
            raise TranslationPipelineError("model_config", f"模型配置无效：{exc}") from exc

        protector = self.protector or MarkdownProtector(
            translatable_front_matter_fields=settings.front_matter_translatable_fields,
        )

        try:
            try:
                glossary = self.glossary_loader(self.project_root / "glossary.json")
            except (ValueError, OSError) as exc:
                raise TranslationPipelineError("glossary", f"术语表加载失败：{exc}") from exc

            emit_log(
                "[配置] 模型："
                f"{settings.llm.model or '<empty>'}，"
                f"批大小：{settings.llm.batch_size}，"
                f"最大重试：{settings.llm.max_retries}"
            )
            emit_log(
                "[配置] Front matter 可翻字段："
                f"{', '.join(settings.front_matter_translatable_fields)}"
            )
            if glossary:
                emit_log(f"[术语] 已加载术语条数：{len(glossary)}")
            else:
                emit_log("[术语] 未加载术语表，使用空术语表。")

            emit_log("[模型] 开始连通性检查。")
            emit_progress("正在检查模型连接", 20)

            connection_started_at = perf_counter()
            try:
                connection_message = client.check_connection()
            except LLMClientError as exc:
                raise TranslationPipelineError("check_connection", f"模型连接失败：{exc}") from exc

            if on_connection_checked is not None:
                on_connection_checked(connection_message)

            emit_log(
                "[模型] 连通性检查通过："
                f"{connection_message}，耗时 {format_elapsed(perf_counter() - connection_started_at)}。"
            )
            emit_progress("模型连接通过", 30)

            emit_log("[解析] 开始解析 Markdown 结构。")
            parse_started_at = perf_counter()
            document = self.parser.parse(source_text)
            protected_document = protector.protect(document)
            segmented_document = self.segmenter.segment(protected_document)
            emit_log(
                f"[解析] Markdown 解析完成，耗时 {format_elapsed(perf_counter() - parse_started_at)}。"
            )
            emit_log(f"[解析] Markdown 块总数：{len(document.blocks)}")
            emit_log(
                "[解析] 可翻译块数："
                f"{sum(1 for block in protected_document.blocks if block.translatable)}"
            )
            emit_log(f"[翻译] 片段总数：{len(segmented_document.segments)}")
            emit_log(
                f"[翻译] 总批次数："
                f"{(len(segmented_document.segments) + settings.llm.batch_size - 1) // settings.llm.batch_size if segmented_document.segments else 0}"
            )
            emit_progress("Markdown 解析完成", 40)

            task_service = self.task_service_factory(client)

            def handle_batch_complete(batch_index: int, total_batches: int) -> None:
                progress = 50 + int((batch_index / total_batches) * 40)
                emit_progress(
                    f"已完成批次 {batch_index}/{total_batches}",
                    progress,
                )

            emit_log("[翻译] 开始批量翻译。")
            emit_progress("开始批量翻译", 45)
            emit_progress("正在等待首批结果", 50)
            translation_started_at = perf_counter()
            try:
                translation_result = task_service.translate_segmented_document(
                    segmented_document,
                    direction=task.direction,
                    glossary=glossary,
                    on_batch_complete=handle_batch_complete,
                    on_log=emit_log,
                )
            except LLMClientError as exc:
                raise TranslationPipelineError("translate", f"翻译执行失败：{exc}") from exc
            emit_log(
                f"[翻译] 批量翻译完成，耗时 {format_elapsed(perf_counter() - translation_started_at)}。"
            )

            emit_log("[输出] 开始写入输出文件。")
            emit_progress("正在写入输出文件", 92)
            output_started_at = perf_counter()
            try:
                output_result = self.output_writer.write_output(
                    source_path=task.source_path,
                    output_dir=task.output_dir,
                    direction=task.direction,
                    markdown_text=translation_result.final_markdown_text,
                )
            except OutputWriteError as exc:
                raise TranslationPipelineError("write_output", f"输出文件写入失败：{exc}") from exc

            emit_log(
                f"[输出] 输出文件写入完成，耗时 {format_elapsed(perf_counter() - output_started_at)}。"
            )
            emit_log(f"[输出] 输出文件路径：{output_result.output_path}")
            emit_log(f"[完成] 总耗时：{format_elapsed(perf_counter() - overall_started_at)}。")
            emit_progress("翻译完成", 100)
            return self._build_pipeline_result(
                output_result=output_result,
                translation_result=translation_result,
                connection_message=connection_message,
            )
        finally:
            if client is not None:
                client.close()

    def _build_pipeline_result(
        self,
        *,
        output_result: OutputWriteResult,
        translation_result: BatchTranslationResult,
        connection_message: str,
    ) -> TranslationPipelineResult:
        return TranslationPipelineResult(
            output_path=output_result.output_path,
            final_markdown_text=translation_result.final_markdown_text,
            connection_message=connection_message,
            total_segments=translation_result.total_segments,
            total_batches=translation_result.total_batches,
            retry_attempts=translation_result.retry_attempts,
        )
