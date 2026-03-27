from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from time import perf_counter
from typing import Callable

from doc_translation_tool.config import AppSettings, load_app_settings
from doc_translation_tool.document_types import (
    detect_document_type,
    supported_source_error_message,
)
from doc_translation_tool.documents import (
    DocumentHandler,
    DocumentParseError,
    MarkdownDocumentHandler,
    get_handler_for_document_type,
)
from doc_translation_tool.llm import LLMClientError, create_llm_client
from doc_translation_tool.markdown import MarkdownParser, MarkdownProtector, MarkdownSegmenter
from doc_translation_tool.models.schema import TranslationTask
from doc_translation_tool.services.glossary_loader import load_glossary
from doc_translation_tool.services.output_writer import (
    DocumentOutputWriter,
    OutputWriteError,
    OutputWriteResult,
)
from doc_translation_tool.services.task_service import BatchTranslationResult, TranslationTaskService
from doc_translation_tool.services.translation_cache import (
    TranslationCheckpoint,
    TranslationCheckpointCache,
)


@dataclass(slots=True)
class TranslationPipelineResult:
    """Final output of the translation pipeline."""

    output_path: str
    final_markdown_text: str
    connection_message: str
    total_segments: int
    total_batches: int
    retry_attempts: int = 0
    reused_cached_segments: int = 0
    rate_limit_backoff_count: int = 0
    split_batch_fallback_count: int = 0
    single_segment_placeholder_fallback_count: int = 0
    overall_elapsed_seconds: float = 0.0


class TranslationPipelineError(RuntimeError):
    """Stage-aware pipeline failure that can be surfaced in the GUI."""

    def __init__(self, stage: str, message: str) -> None:
        super().__init__(message)
        self.stage = stage
        self.message = message


class DocumentTranslationPipeline:
    """Run the full document translation flow from input file to output file."""

    _TRANSLATION_PROGRESS_START = 45
    _TRANSLATION_PROGRESS_END = 95
    _WRITE_OUTPUT_PROGRESS = 97

    def __init__(
        self,
        *,
        project_root: str | Path,
        settings_loader: Callable[[str | Path], AppSettings] = load_app_settings,
        client_factory=create_llm_client,
        parser: MarkdownParser | None = None,
        protector: MarkdownProtector | None = None,
        segmenter: MarkdownSegmenter | None = None,
        output_writer: DocumentOutputWriter | None = None,
        task_service_factory: Callable[[object, DocumentHandler], TranslationTaskService]
        | None = None,
        document_type_detector: Callable[[str | Path], str | None] = detect_document_type,
        glossary_loader: Callable[[str | Path], list[dict[str, str]]] = load_glossary,
        checkpoint_cache: TranslationCheckpointCache | None = None,
    ) -> None:
        self.project_root = Path(project_root)
        self.settings_loader = settings_loader
        self.client_factory = client_factory
        self.document_type_detector = document_type_detector
        self.markdown_handler = MarkdownDocumentHandler(
            parser=parser,
            protector=protector,
            segmenter=segmenter,
        )
        self.output_writer = output_writer or DocumentOutputWriter()
        self.task_service_factory = task_service_factory or (
            lambda client, handler: TranslationTaskService(
                client,
                rebuilder=handler,
            )
        )
        self.glossary_loader = glossary_loader
        self.checkpoint_cache = checkpoint_cache or TranslationCheckpointCache()

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

        def translation_progress(completed_batches: int, total_batches: int) -> int:
            if total_batches <= 0:
                return self._TRANSLATION_PROGRESS_START
            if completed_batches <= 0:
                return self._TRANSLATION_PROGRESS_START

            stage_span = (
                self._TRANSLATION_PROGRESS_END - self._TRANSLATION_PROGRESS_START
            )
            return min(
                self._TRANSLATION_PROGRESS_END,
                self._TRANSLATION_PROGRESS_START
                + math.ceil((completed_batches / total_batches) * stage_span),
            )

        def translation_running_progress(
            completed_batches: int,
            total_batches: int,
        ) -> int:
            base_progress = translation_progress(completed_batches, total_batches)
            if completed_batches >= total_batches:
                return base_progress
            return min(base_progress + 1, self._TRANSLATION_PROGRESS_END - 1)

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
        handler = None
        try:
            try:
                settings = self.settings_loader(self.project_root)
                client = self.client_factory(settings.llm)
            except (ValueError, OSError) as exc:
                raise TranslationPipelineError("model_config", f"模型配置无效：{exc}") from exc

            try:
                handler = self._resolve_document_handler(task.source_path)
            except ValueError as exc:
                raise TranslationPipelineError("source_type", str(exc)) from exc

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

            assert handler is not None
            emit_log(f"[文档] 类型：{handler.document_type}")
            emit_log(f"[解析] 开始解析 {handler.document_type} 文档结构。")
            parse_started_at = perf_counter()
            try:
                prepared_document = handler.prepare_document(
                    source_text,
                    settings=settings,
                )
            except DocumentParseError as exc:
                raise TranslationPipelineError("parse_document", str(exc)) from exc
            emit_log(
                f"[解析] {handler.document_type} 解析完成，耗时 {format_elapsed(perf_counter() - parse_started_at)}。"
            )
            emit_log(f"[解析] 文档块总数：{len(prepared_document.blocks)}")
            emit_log(
                "[解析] 可翻译块数："
                f"{sum(1 for block in prepared_document.blocks if block.translatable)}"
            )
            total_translation_batches = (
                (len(prepared_document.segments) + settings.llm.batch_size - 1)
                // settings.llm.batch_size
                if prepared_document.segments
                else 0
            )
            emit_log(f"[翻译] 片段总数：{len(prepared_document.segments)}")
            emit_log(f"[翻译] 总批次数：{total_translation_batches}")
            emit_progress("文档解析完成", 40)

            cache_path = self.checkpoint_cache.build_cache_path(
                source_path=task.source_path,
                output_dir=task.output_dir,
                direction=task.direction,
            )
            document_fingerprint = self.checkpoint_cache.build_document_fingerprint(
                prepared_document
            )
            cached_translations = self.checkpoint_cache.load(
                cache_path,
                source_path=task.source_path,
                direction=task.direction,
                document_fingerprint=document_fingerprint,
            )
            if cached_translations:
                emit_log(
                    "[续跑] 已加载缓存片段："
                    f"{len(cached_translations)}/{len(prepared_document.segments)}"
                )

            task_service = self.task_service_factory(client, handler)

            def handle_batch_complete(batch_index: int, total_batches: int) -> None:
                progress = translation_progress(batch_index, total_batches)
                emit_progress(
                    f"翻译中：已完成批次 {batch_index}/{total_batches}",
                    progress,
                )

            def handle_batch_started(
                batch_index: int,
                total_batches: int,
                completed_batches: int,
            ) -> None:
                progress = translation_running_progress(completed_batches, total_batches)
                emit_progress(
                    f"翻译中：正在处理第 {batch_index}/{total_batches} 批",
                    progress,
                )

            emit_log("[翻译] 开始批量翻译。")
            emit_progress("开始批量翻译", self._TRANSLATION_PROGRESS_START)
            emit_progress(
                f"翻译中：已完成批次 0/{total_translation_batches}",
                self._TRANSLATION_PROGRESS_START,
            )
            translation_started_at = perf_counter()

            checkpoint_translations = dict(cached_translations)

            def persist_checkpoint(new_translations: dict[str, str]) -> None:
                checkpoint_translations.update(new_translations)
                self.checkpoint_cache.save(
                    cache_path,
                    TranslationCheckpoint(
                        source_path=str(task.source_path),
                        direction=task.direction,
                        document_fingerprint=document_fingerprint,
                        translated_segment_texts=checkpoint_translations,
                    ),
                )

            try:
                translation_result = task_service.translate_prepared_document(
                    prepared_document,
                    direction=task.direction,
                    glossary=glossary,
                    existing_translations=cached_translations,
                    on_batch_complete=handle_batch_complete,
                    on_batch_started=handle_batch_started,
                    on_batch_translated=persist_checkpoint,
                    on_log=emit_log,
                )
            except LLMClientError as exc:
                raise TranslationPipelineError("translate", f"翻译执行失败：{exc}") from exc
            emit_log(
                f"[翻译] 批量翻译完成，耗时 {format_elapsed(perf_counter() - translation_started_at)}。"
            )
            emit_log(
                "[stats] [翻译] 汇总："
                f"复用缓存片段 {translation_result.reused_cached_segments}，"
                f"重试 {translation_result.retry_attempts} 次，"
                f"429降并发 {translation_result.rate_limit_backoff_count} 次，"
                f"拆批回退 {translation_result.split_batch_fallback_count} 次，"
                "单片段保序救援 "
                f"{translation_result.single_segment_placeholder_fallback_count} 次。"
            )

            emit_log("[输出] 开始写入输出文件。")
            emit_progress("正在写入输出文件", self._WRITE_OUTPUT_PROGRESS)
            output_started_at = perf_counter()
            try:
                output_result = self.output_writer.write_output(
                    source_path=task.source_path,
                    output_dir=task.output_dir,
                    direction=task.direction,
                    document_text=translation_result.final_markdown_text,
                    output_extension=handler.output_extension(task.source_path),
                )
            except OutputWriteError as exc:
                raise TranslationPipelineError("write_output", f"输出文件写入失败：{exc}") from exc

            emit_log(
                f"[输出] 输出文件写入完成，耗时 {format_elapsed(perf_counter() - output_started_at)}。"
            )
            emit_log(f"[输出] 输出文件路径：{output_result.output_path}")
            self.checkpoint_cache.clear(cache_path)
            overall_elapsed_seconds = perf_counter() - overall_started_at
            emit_log(f"[完成] 总耗时：{format_elapsed(overall_elapsed_seconds)}。")
            emit_progress("翻译完成", 100)
            return self._build_pipeline_result(
                output_result=output_result,
                translation_result=translation_result,
                connection_message=connection_message,
                overall_elapsed_seconds=overall_elapsed_seconds,
            )
        finally:
            if client is not None:
                client.close()

    def _resolve_document_handler(self, source_path: str | Path) -> DocumentHandler:
        document_type = self.document_type_detector(source_path)
        if document_type is None:
            raise ValueError(supported_source_error_message())
        if document_type == self.markdown_handler.document_type:
            return self.markdown_handler
        return get_handler_for_document_type(document_type)

    def _build_pipeline_result(
        self,
        *,
        output_result: OutputWriteResult,
        translation_result: BatchTranslationResult,
        connection_message: str,
        overall_elapsed_seconds: float,
    ) -> TranslationPipelineResult:
        return TranslationPipelineResult(
            output_path=output_result.output_path,
            final_markdown_text=translation_result.final_markdown_text,
            connection_message=connection_message,
            total_segments=translation_result.total_segments,
            total_batches=translation_result.total_batches,
            retry_attempts=translation_result.retry_attempts,
            reused_cached_segments=translation_result.reused_cached_segments,
            rate_limit_backoff_count=translation_result.rate_limit_backoff_count,
            split_batch_fallback_count=translation_result.split_batch_fallback_count,
            single_segment_placeholder_fallback_count=(
                translation_result.single_segment_placeholder_fallback_count
            ),
            overall_elapsed_seconds=overall_elapsed_seconds,
        )
