from __future__ import annotations

from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
import re
import threading
from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable

from doc_translation_tool.documents.base import PreparedDocument
from doc_translation_tool.llm import (
    BaseLLMClient,
    LLMClientError,
    TranslationItem,
    TranslationResult,
)
from doc_translation_tool.markdown.rebuilder import MarkdownRebuilder
from doc_translation_tool.utils.logger import PipelineLogger


@dataclass(slots=True)
class BatchTranslationResult:
    """Result of translating a segmented Markdown document in batches."""

    translated_segment_texts: dict[str, str]
    rebuilt_protected_block_texts: list[str]
    final_markdown_text: str
    total_segments: int
    total_batches: int
    successful_batches: int
    retry_attempts: int = 0
    reused_cached_segments: int = 0
    rate_limit_backoff_count: int = 0
    split_batch_fallback_count: int = 0
    single_segment_placeholder_fallback_count: int = 0
    batch_errors: list[str] = field(default_factory=list)


class TranslationTaskService:
    """Batch translation orchestration on top of the LLM client."""

    _VALIDATION_MODE_PRESETS = {
        "strict": (3, False, 1),
        "balanced": (5, False, 2),
        "lenient": (8, True, 3),
    }
    _PLACEHOLDER_RE = re.compile(r"@@PROTECT_\d+@@")
    _PLACEHOLDER_ESCAPED_AT_RE = re.compile(r"\\@")
    _PLACEHOLDER_LOOSE_RE = re.compile(
        r"@@\s*protect\s*[_-]\s*(\d+)\s*@@",
        flags=re.IGNORECASE,
    )
    _ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
    _EN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]*\b")
    _DIRECTIONAL_KEYWORDS_RE = re.compile(
        r"\b(from|to|before|after|先|后|从|到|之前|之后)\b",
        flags=re.IGNORECASE,
    )
    _SPLITTABLE_ERROR_PATTERNS = (
        "Translated text changed protected placeholder tokens or their order.",
        "Translated text still contains Chinese outside protected placeholders.",
        "Translated text still contains too much English outside protected placeholders.",
        "Translated item IDs do not match the request order.",
    )
    _RESIDUAL_LANGUAGE_ERROR_PATTERNS = (
        "Translated text still contains Chinese outside protected placeholders.",
        "Translated text still contains too much English outside protected placeholders.",
    )

    def __init__(
        self,
        client: BaseLLMClient,
        *,
        rebuilder=None,
        batch_size: int | None = None,
        parallel_batches: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.client = client
        self.rebuilder = rebuilder or MarkdownRebuilder()
        self.batch_size = batch_size or client.settings.batch_size
        self.parallel_batches = (
            parallel_batches
            if parallel_batches is not None
            else client.settings.parallel_batches
        )
        self.max_retries = (
            max_retries if max_retries is not None else client.settings.max_retries
        )

        (
            self.residual_language_threshold,
            self.allow_placeholder_reorder,
            self.min_batch_split_size,
        ) = self._resolve_validation_settings(client.settings)

        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")
        if self.parallel_batches <= 0:
            raise ValueError("parallel_batches must be greater than zero.")
        if self.max_retries < 0:
            raise ValueError("max_retries must be zero or greater.")
        self._metrics_lock = threading.Lock()
        self._result_lock = threading.Lock()
        self._reset_metrics()

    def translate_prepared_document(
        self,
        document: PreparedDocument,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None = None,
        existing_translations: dict[str, str] | None = None,
        on_batch_complete: Callable[[int, int], None] | None = None,
        on_batch_started: Callable[[int, int, int], None] | None = None,
        on_batch_translated: Callable[[dict[str, str]], None] | None = None,
        on_log: Callable[[str], None] | None = None,
        on_progress: Callable[[int, int, float], None] | None = None,  # New: (completed_segments, total_segments, estimated_seconds_remaining)
    ) -> BatchTranslationResult:
        logger = PipelineLogger(on_log)

        segments = document.segments
        valid_segment_ids = {segment.id for segment in segments}
        translated_segment_texts: dict[str, str] = {
            segment_id: translated_text
            for segment_id, translated_text in (existing_translations or {}).items()
            if segment_id in valid_segment_ids
        }
        remaining_segments = [
            segment for segment in segments if segment.id not in translated_segment_texts
        ]
        total_batches = self._count_batches(len(remaining_segments))
        successful_batches = 0
        batch_errors: list[str] = []
        self._reset_metrics()
        reused_cached_segments = len(translated_segment_texts)

        # Initialize progress tracking
        self._total_segments = len(segments)
        self._completed_segments = reused_cached_segments
        self._batch_times: list[float] = []
        self._progress_callback = on_progress

        if existing_translations and translated_segment_texts:
            logger.resume(
                f"已复用缓存片段："
                f"{len(translated_segment_texts)}/{len(segments)}"
            )

        if not segments:
            logger.translate("没有可翻译片段，直接回填输出。")
            return self._build_result(
                document=document,
                translated_segment_texts=translated_segment_texts,
                total_segments=0,
                total_batches=0,
                successful_batches=0,
                retry_attempts=0,
                reused_cached_segments=reused_cached_segments,
                rate_limit_backoff_count=0,
                split_batch_fallback_count=0,
                single_segment_placeholder_fallback_count=0,
                batch_errors=[],
            )

        if not remaining_segments:
            return self._build_result(
                document=document,
                translated_segment_texts=translated_segment_texts,
                total_segments=len(segments),
                total_batches=0,
                successful_batches=0,
                retry_attempts=0,
                reused_cached_segments=reused_cached_segments,
                rate_limit_backoff_count=0,
                split_batch_fallback_count=0,
                single_segment_placeholder_fallback_count=0,
                batch_errors=[],
            )

        indexed_batches = list(enumerate(self._iter_batches(remaining_segments), start=1))

        if self.parallel_batches == 1 or total_batches <= 1:
            successful_batches = self._translate_batches_sequential(
                indexed_batches,
                direction=direction,
                glossary=glossary,
                total_batches=total_batches,
                translated_segment_texts=translated_segment_texts,
                successful_batches=successful_batches,
                on_batch_translated=on_batch_translated,
                on_batch_complete=on_batch_complete,
                on_batch_started=on_batch_started,
                on_log=on_log,
            )
        else:
            successful_batches = self._translate_batches_parallel_adaptive(
                indexed_batches,
                direction=direction,
                glossary=glossary,
                total_batches=total_batches,
                translated_segment_texts=translated_segment_texts,
                successful_batches=successful_batches,
                batch_errors=batch_errors,
                on_batch_translated=on_batch_translated,
                on_batch_complete=on_batch_complete,
                on_batch_started=on_batch_started,
                on_log=on_log,
            )

        return self._build_result(
            document=document,
            translated_segment_texts=translated_segment_texts,
            total_segments=len(segments),
            total_batches=total_batches,
            successful_batches=successful_batches,
            retry_attempts=self._retry_attempts,
            reused_cached_segments=reused_cached_segments,
            rate_limit_backoff_count=self._rate_limit_backoff_count,
            split_batch_fallback_count=self._split_batch_fallback_count,
            single_segment_placeholder_fallback_count=self._single_segment_placeholder_fallback_count,
            batch_errors=batch_errors,
        )

    def translate_segmented_document(
        self,
        document: PreparedDocument,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None = None,
        existing_translations: dict[str, str] | None = None,
        on_batch_complete: Callable[[int, int], None] | None = None,
        on_batch_started: Callable[[int, int, int], None] | None = None,
        on_batch_translated: Callable[[dict[str, str]], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> BatchTranslationResult:
        return self.translate_prepared_document(
            document,
            direction=direction,
            glossary=glossary,
            existing_translations=existing_translations,
            on_batch_complete=on_batch_complete,
            on_batch_started=on_batch_started,
            on_batch_translated=on_batch_translated,
            on_log=on_log,
        )

    def rebuild_protected_block_texts(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str],
    ) -> list[str]:
        return self.rebuilder.rebuild_protected_block_texts(
            document,
            translated_segment_texts,
        )

    def rebuild_markdown_text(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str],
    ) -> str:
        return self.rebuilder.rebuild_document(
            document,
            translated_segment_texts,
        )

    def _build_result(
        self,
        *,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str],
        total_segments: int,
        total_batches: int,
        successful_batches: int,
        retry_attempts: int,
        reused_cached_segments: int,
        rate_limit_backoff_count: int,
        split_batch_fallback_count: int,
        single_segment_placeholder_fallback_count: int,
        batch_errors: list[str],
    ) -> BatchTranslationResult:
        rebuilt_blocks, final_markdown_text = self._rebuild_document_outputs(
            document,
            translated_segment_texts,
        )
        return BatchTranslationResult(
            translated_segment_texts=translated_segment_texts,
            rebuilt_protected_block_texts=rebuilt_blocks,
            final_markdown_text=final_markdown_text,
            total_segments=total_segments,
            total_batches=total_batches,
            successful_batches=successful_batches,
            retry_attempts=retry_attempts,
            reused_cached_segments=reused_cached_segments,
            rate_limit_backoff_count=rate_limit_backoff_count,
            split_batch_fallback_count=split_batch_fallback_count,
            single_segment_placeholder_fallback_count=single_segment_placeholder_fallback_count,
            batch_errors=batch_errors,
        )

    def _rebuild_document_outputs(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str],
    ) -> tuple[list[str], str]:
        rebuilt_blocks = self.rebuild_protected_block_texts(
            document,
            translated_segment_texts,
        )
        final_markdown_text = self.rebuild_markdown_text(
            document,
            translated_segment_texts,
        )
        return rebuilt_blocks, final_markdown_text

    def _translate_batches_sequential(
        self,
        indexed_batches,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None,
        total_batches: int,
        translated_segment_texts: dict[str, str],
        successful_batches: int,
        on_batch_translated: Callable[[dict[str, str]], None] | None,
        on_batch_complete: Callable[[int, int], None] | None,
        on_batch_started: Callable[[int, int, int], None] | None,
        on_log: Callable[[str], None] | None,
    ) -> int:
        for batch_index, batch in indexed_batches:
            if on_batch_started is not None:
                on_batch_started(batch_index, total_batches, successful_batches)
            batch_result = self._run_single_batch(
                batch,
                direction=direction,
                glossary=glossary,
                batch_index=batch_index,
                total_batches=total_batches,
                on_log=on_log,
            )
            self._store_batch_result_items(
                translated_segment_texts,
                batch_result,
                on_batch_translated=on_batch_translated,
            )
            successful_batches += 1
            if on_batch_complete is not None:
                on_batch_complete(successful_batches, total_batches)
        return successful_batches

    def _translate_batches_parallel_adaptive(
        self,
        indexed_batches,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None,
        total_batches: int,
        translated_segment_texts: dict[str, str],
        successful_batches: int,
        batch_errors: list[str],
        on_batch_translated: Callable[[dict[str, str]], None] | None,
        on_batch_complete: Callable[[int, int], None] | None,
        on_batch_started: Callable[[int, int, int], None] | None,
        on_log: Callable[[str], None] | None,
    ) -> int:
        logger = PipelineLogger(on_log)
        remaining_batches = list(indexed_batches)
        current_parallel_batches = min(self.parallel_batches, total_batches)

        while remaining_batches:
            if current_parallel_batches <= 1 or len(remaining_batches) <= 1:
                return self._translate_batches_sequential(
                    remaining_batches,
                    direction=direction,
                    glossary=glossary,
                    total_batches=total_batches,
                    translated_segment_texts=translated_segment_texts,
                    successful_batches=successful_batches,
                    on_batch_translated=on_batch_translated,
                    on_batch_complete=on_batch_complete,
                    on_batch_started=on_batch_started,
                    on_log=on_log,
                )

            max_workers = min(current_parallel_batches, len(remaining_batches))
            retry_batches: list[tuple[int, object]] | None = None

            with ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="doc-translate-batch",
            ) as executor:
                pending: dict[object, tuple[int, object]] = {}
                next_batch_offset = 0

                def submit_batch(batch_info: tuple[int, object], completed_batches: int) -> None:
                    batch_index, batch = batch_info
                    future = executor.submit(
                        self._run_single_batch,
                        batch,
                        direction=direction,
                        glossary=glossary,
                        batch_index=batch_index,
                        total_batches=total_batches,
                        on_log=on_log,
                    )
                    pending[future] = batch_info
                    if on_batch_started is not None:
                        on_batch_started(batch_index, total_batches, completed_batches)

                while next_batch_offset < max_workers:
                    submit_batch(remaining_batches[next_batch_offset], successful_batches)
                    next_batch_offset += 1

                while pending:
                    done, _ = wait(
                        pending,
                        return_when=FIRST_COMPLETED,
                    )

                    rate_limited_failures: list[tuple[int, object]] = []
                    fatal_error: LLMClientError | None = None

                    for future in done:
                        batch_info = pending.pop(future)
                        try:
                            batch_result = future.result()
                        except LLMClientError as exc:
                            batch_errors.append(str(exc))
                            if fatal_error is None and self._is_rate_limit_error(exc):
                                rate_limited_failures.append(batch_info)
                                continue
                            if fatal_error is None:
                                fatal_error = exc
                            continue

                        self._store_batch_result_items(
                            translated_segment_texts,
                            batch_result,
                            on_batch_translated=on_batch_translated,
                        )
                        successful_batches += 1
                        if on_batch_complete is not None:
                            on_batch_complete(successful_batches, total_batches)
                        if (
                            next_batch_offset < len(remaining_batches)
                            and len(pending) < current_parallel_batches
                        ):
                            submit_batch(
                                remaining_batches[next_batch_offset],
                                successful_batches,
                            )
                            next_batch_offset += 1

                    if fatal_error is not None:
                        for pending_future in pending:
                            pending_future.cancel()
                        raise fatal_error

                    if rate_limited_failures:
                        for pending_future in pending:
                            pending_future.cancel()
                        retry_batches = sorted(
                            [
                                *rate_limited_failures,
                                *pending.values(),
                                *remaining_batches[next_batch_offset:],
                            ],
                            key=lambda item: item[0],
                        )
                        lowered_parallel_batches = max(1, current_parallel_batches // 2)
                        failed_batch_labels = ", ".join(
                            str(batch_index) for batch_index, _ in rate_limited_failures
                        )
                        logger.log(
                            "[限流] 检测到 429/限流错误，"
                            f"批次 {failed_batch_labels} 将降并发重试："
                            f"{current_parallel_batches} -> {lowered_parallel_batches}"
                        )
                        self._record_rate_limit_backoff()
                        current_parallel_batches = lowered_parallel_batches
                        break

            if retry_batches is None:
                return successful_batches

            remaining_batches = retry_batches

        return successful_batches

    def _store_batch_result_items(
        self,
        translated_segment_texts: dict[str, str],
        batch_result,
        *,
        on_batch_translated: Callable[[dict[str, str]], None] | None = None,
    ) -> None:
        new_translations: dict[str, str] = {}
        with self._result_lock:
            for item in batch_result:
                translated_segment_texts[item.id] = item.translated_text
                new_translations[item.id] = item.translated_text

            # Update progress tracking
            self._completed_segments += len(batch_result)

        if on_batch_translated is not None and new_translations:
            on_batch_translated(new_translations)

        # Call progress callback with estimated time
        if self._progress_callback is not None:
            estimated_remaining = self._estimate_remaining_time()
            self._progress_callback(
                self._completed_segments,
                self._total_segments,
                estimated_remaining
            )

    def _run_single_batch(
        self,
        batch,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None,
        batch_index: int,
        total_batches: int,
        on_log: Callable[[str], None] | None,
    ):
        logger = PipelineLogger(on_log)
        batch_ids = ", ".join(segment.id for segment in batch)
        logger.log(
            f"[翻译] 开始批次 {batch_index}/{total_batches}，"
            f"片段：{batch_ids}"
        )

        batch_started_at = perf_counter()
        result = self._translate_batch_with_fallback(
            batch,
            direction=direction,
            glossary=glossary,
            batch_index=batch_index,
            total_batches=total_batches,
            on_log=on_log,
        )

        # Track batch time for estimation
        batch_elapsed = perf_counter() - batch_started_at
        self._batch_times.append(batch_elapsed)

        logger.log(
            f"[翻译] 批次 {batch_index}/{total_batches} 完成，"
            f"耗时 {perf_counter() - batch_started_at:.2f}s。"
        )
        return result

    def _translate_batch_with_retry(
        self,
        batch,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None,
        batch_index: int,
        total_batches: int,
        on_log: Callable[[str], None] | None,
    ):
        logger = PipelineLogger(on_log)
        last_error: LLMClientError | None = None
        batch_ids = ", ".join(segment.id for segment in batch)

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self._record_retry_attempt()
            logger.log(
                f"[翻译] 批次 {batch_index}/{total_batches} 第 {attempt + 1} 次尝试，"
                f"片段：{batch_ids}"
            )
            try:
                result = self.client.translate_batch(
                    items=[
                        TranslationItem(id=segment.id, text=segment.text)
                        for segment in batch
                    ],
                    direction=direction,
                    glossary=glossary,
                )
                self._validate_translated_batch(
                    batch,
                    result,
                    direction=direction,
                )
                if attempt > 0:
                    logger.log(
                        f"[重试] 批次 {batch_index}/{total_batches} 重试成功，"
                        f"片段：{batch_ids}"
                    )
                return result
            except LLMClientError as exc:
                last_error = exc
                # Determine retry reason for better transparency
                retry_reason = self._classify_retry_reason(exc)
                if attempt < self.max_retries:
                    logger.log(
                        f"[重试] 批次 {batch_index}/{total_batches} 第 {attempt + 1} 次失败，"
                        f"准备重试。片段：{batch_ids}。原因：{retry_reason}"
                    )
                else:
                    logger.log(
                        f"[失败] 批次 {batch_index}/{total_batches} 最终失败。"
                        f"片段：{batch_ids}。原因：{retry_reason}"
                    )
                if attempt == self.max_retries:
                    break

        if last_error is None:
            raise LLMClientError(
                f"Batch translation failed for batch {batch_index}/{total_batches} "
                f"(segments: {batch_ids}) with no error captured"
            )
        raise LLMClientError(
            "Batch translation failed for "
            f"batch {batch_index}/{total_batches} "
            f"(segments: {batch_ids}) after {self.max_retries + 1} attempts: {last_error}"
        ) from last_error

    def _translate_batch_with_fallback(
        self,
        batch,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None,
        batch_index: int,
        total_batches: int,
        on_log: Callable[[str], None] | None,
    ):
        logger = PipelineLogger(on_log)
        try:
            return self._translate_batch_with_retry(
                batch,
                direction=direction,
                glossary=glossary,
                batch_index=batch_index,
                total_batches=total_batches,
                on_log=on_log,
            )
        except LLMClientError as exc:
            if self._should_retry_single_segment_placeholder_order_error(batch, exc):
                self._record_single_segment_placeholder_fallback()
                logger.log(
                    f"[救援] 批次 {batch_index}/{total_batches} 触发单片段占位符顺序救援，"
                    f"原因：占位符顺序验证失败"
                )
                return self._translate_single_segment_with_placeholder_fallback(
                    batch[0],
                    direction=direction,
                    glossary=glossary,
                    batch_index=batch_index,
                    total_batches=total_batches,
                    on_log=on_log,
                )

            if self._should_retry_single_segment_residual_language_error(batch, exc):
                logger.log(
                    f"[救援] 批次 {batch_index}/{total_batches} 触发单片段残留语言救援，"
                    f"原因：残留语言检测失败"
                )
                return self._translate_single_segment_with_language_fallback(
                    batch[0],
                    direction=direction,
                    glossary=glossary,
                    batch_index=batch_index,
                    total_batches=total_batches,
                    on_log=on_log,
                )

            if len(batch) <= 1 or not self._should_split_failed_batch(exc):
                raise

            # Use configured minimum batch split size
            min_split_size = getattr(self, 'min_batch_split_size', 3)
            if len(batch) < min_split_size:
                raise

            retry_reason = self._classify_retry_reason(exc)
            logger.log(
                f"[拆批] 批次 {batch_index}/{total_batches} 拆分为两个子批次重试，"
                f"原因：{retry_reason}"
            )

            midpoint = len(batch) // 2
            left_batch = batch[:midpoint]
            right_batch = batch[midpoint:]
            self._record_split_batch_fallback()

            logger.log(
                f"[降批] 批次 {batch_index}/{total_batches} 因结构校验失败，"
                f"拆分为 {len(left_batch)} + {len(right_batch)} 个片段继续重试。"
            )
            logger.log(
                "[降批] 左侧片段："
                + ", ".join(segment.id for segment in left_batch)
            )
            logger.log(
                "[降批] 右侧片段："
                + ", ".join(segment.id for segment in right_batch)
            )

            left_results = self._translate_batch_with_fallback(
                left_batch,
                direction=direction,
                glossary=glossary,
                batch_index=batch_index,
                total_batches=total_batches,
                on_log=on_log,
            )
            right_results = self._translate_batch_with_fallback(
                right_batch,
                direction=direction,
                glossary=glossary,
                batch_index=batch_index,
                total_batches=total_batches,
                on_log=on_log,
            )
            return [*left_results, *right_results]

    def _should_retry_single_segment_placeholder_order_error(
        self,
        batch,
        error: LLMClientError,
    ) -> bool:
        if len(batch) != 1:
            return False

        if (
            "Translated text changed protected placeholder tokens or their order."
            not in str(error)
        ):
            return False

        return len(self._PLACEHOLDER_RE.findall(batch[0].text)) >= 2

    def _translate_single_segment_with_placeholder_fallback(
        self,
        segment,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None,
        batch_index: int,
        total_batches: int,
        on_log: Callable[[str], None] | None,
    ):
        logger = PipelineLogger(on_log)
        chunk_items = self._split_single_segment_by_placeholders(segment)

        if len(chunk_items) <= 1:
            raise LLMClientError(
                "Single-segment placeholder fallback could not split the segment."
            )

        logger.log(
            f"[降级] 批次 {batch_index}/{total_batches} 中的单片段 {segment.id} "
            f"因占位符顺序错误，拆成 {len(chunk_items)} 个保序子片段重试。"
        )

        chunk_results = self._translate_batch_with_fallback(
            chunk_items,
            direction=direction,
            glossary=glossary,
            batch_index=batch_index,
            total_batches=total_batches,
            on_log=on_log,
        )
        merged_text = self._normalize_placeholder_tokens(
            "".join(item.translated_text for item in chunk_results)
        )
        source_placeholders = self._PLACEHOLDER_RE.findall(segment.text)
        translated_placeholders = self._PLACEHOLDER_RE.findall(merged_text)

        # Use configured validation logic for placeholder order
        if not self._validate_placeholders(segment.text, source_placeholders, translated_placeholders):
            raise LLMClientError(
                "Translated text changed protected placeholder tokens or their order."
            )

        merged_results = [
            TranslationResult(id=segment.id, translated_text=merged_text)
        ]
        return merged_results

    def _should_retry_single_segment_residual_language_error(
        self,
        batch,
        error: LLMClientError,
    ) -> bool:
        if len(batch) != 1:
            return False

        message = str(error)
        if not any(pattern in message for pattern in self._RESIDUAL_LANGUAGE_ERROR_PATTERNS):
            return False

        return self._can_split_single_segment_for_language_retry(batch[0].text)

    def _translate_single_segment_with_language_fallback(
        self,
        segment,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None,
        batch_index: int,
        total_batches: int,
        on_log: Callable[[str], None] | None,
    ):
        logger = PipelineLogger(on_log)
        chunk_items = self._split_single_segment_for_language_retry(segment)

        if len(chunk_items) <= 1:
            raise LLMClientError(
                "Single-segment residual-language fallback could not split the segment."
            )

        logger.log(
            f"[降级] 批次 {batch_index}/{total_batches} 中的单片段 {segment.id} "
            f"因残留源语言校验失败，拆成 {len(chunk_items)} 个子片段重试。"
        )

        chunk_results = self._translate_batch_with_fallback(
            chunk_items,
            direction=direction,
            glossary=glossary,
            batch_index=batch_index,
            total_batches=total_batches,
            on_log=on_log,
        )
        merged_text = self._normalize_placeholder_tokens(
            "".join(item.translated_text for item in chunk_results)
        )
        source_placeholders = self._PLACEHOLDER_RE.findall(segment.text)
        translated_placeholders = self._PLACEHOLDER_RE.findall(merged_text)

        # Use configured validation logic for placeholder order
        if not self._validate_placeholders(segment.text, source_placeholders, translated_placeholders):
            raise LLMClientError(
                "Translated text changed protected placeholder tokens or their order."
            )

        merged_results = [
            TranslationResult(id=segment.id, translated_text=merged_text)
        ]
        return merged_results

    def _split_single_segment_by_placeholders(self, segment) -> list[TranslationItem]:
        matches = list(self._PLACEHOLDER_RE.finditer(segment.text))
        if len(matches) < 2:
            return [TranslationItem(id=segment.id, text=segment.text)]

        chunk_texts: list[str] = [segment.text[: matches[0].end()]]
        for index in range(1, len(matches) - 1):
            chunk_texts.append(
                segment.text[matches[index - 1].end() : matches[index].end()]
            )
        chunk_texts.append(segment.text[matches[-2].end() :])

        return [
            TranslationItem(
                id=f"{segment.id}__phchunk_{index:02d}",
                text=chunk_text,
            )
            for index, chunk_text in enumerate(chunk_texts)
            if chunk_text
        ]

    def _split_single_segment_for_language_retry(
        self,
        segment,
    ) -> list[TranslationItem]:
        chunk_texts = self._split_text_for_language_retry(segment.text)
        if len(chunk_texts) <= 1:
            return [TranslationItem(id=segment.id, text=segment.text)]

        return [
            TranslationItem(
                id=f"{segment.id}__langchunk_{index:02d}",
                text=chunk_text,
            )
            for index, chunk_text in enumerate(chunk_texts)
            if chunk_text
        ]

    def _can_split_single_segment_for_language_retry(self, text: str) -> bool:
        return len(self._split_text_for_language_retry(text)) > 1

    def _split_text_for_language_retry(self, text: str) -> list[str]:
        line_chunks = [line for line in text.splitlines(keepends=True) if line]
        if len(line_chunks) > 1:
            return line_chunks

        sentence_chunks: list[str] = []
        current: list[str] = []

        for index, char in enumerate(text):
            current.append(char)
            if self._is_sentence_retry_boundary(text, index):
                sentence_chunks.append("".join(current))
                current = []

        if current:
            sentence_chunks.append("".join(current))

        return [chunk for chunk in sentence_chunks if chunk]

    def _is_sentence_retry_boundary(self, text: str, index: int) -> bool:
        char = text[index]
        if char in "。！？":
            return True
        if char not in ".!?":
            return False

        next_char = text[index + 1] if index + 1 < len(text) else ""
        if next_char == "":
            return True
        return next_char.isspace() or next_char in "\"')]}>"

    def _should_split_failed_batch(self, error: LLMClientError) -> bool:
        message = str(error)
        return any(pattern in message for pattern in self._SPLITTABLE_ERROR_PATTERNS)

    def _iter_batches(self, segments):
        for index in range(0, len(segments), self.batch_size):
            yield segments[index : index + self.batch_size]

    def _count_batches(self, total_segments: int) -> int:
        if total_segments == 0:
            return 0
        return (total_segments + self.batch_size - 1) // self.batch_size

    def _validate_translated_batch(
        self,
        batch,
        results,
        *,
        direction: str,
    ) -> None:
        source_items = {
            segment.id: segment.text
            for segment in batch
        }

        for item in results:
            source_text = source_items.get(item.id, "")
            source_placeholders = self._PLACEHOLDER_RE.findall(source_text)
            normalized_translated_text = self._normalize_placeholder_tokens(
                item.translated_text
            )
            translated_placeholders = self._PLACEHOLDER_RE.findall(
                normalized_translated_text
            )

            # Use configured validation logic for placeholder order
            if not self._validate_placeholders(source_text, source_placeholders, translated_placeholders):
                raise LLMClientError(
                    "Translated text changed protected placeholder tokens or their order."
                )

            translated_without_placeholders = self._PLACEHOLDER_RE.sub(
                " ",
                normalized_translated_text,
            )
            item.translated_text = normalized_translated_text
            if direction == "zh_to_en" and self._ZH_CHAR_RE.search(
                translated_without_placeholders
            ):
                raise LLMClientError(
                    "Translated text still contains Chinese outside protected placeholders."
                )
            if direction == "en_to_zh" and self._contains_excessive_english(
                translated_without_placeholders
            ):
                raise LLMClientError(
                    "Translated text still contains too much English outside protected placeholders."
                )

    def _contains_excessive_english(self, text: str) -> bool:
        english_words = self._EN_WORD_RE.findall(text)
        lowercase_words = [
            word
            for word in english_words
            if any(character.islower() for character in word)
        ]
        # Use configured threshold instead of hardcoded 3
        threshold = getattr(self, 'residual_language_threshold', 10)
        return len(lowercase_words) >= threshold

    def _reset_metrics(self) -> None:
        self._retry_attempts = 0
        self._rate_limit_backoff_count = 0
        self._split_batch_fallback_count = 0
        self._single_segment_placeholder_fallback_count = 0
        self._total_segments = 0
        self._completed_segments = 0
        self._batch_times: list[float] = []
        self._progress_callback: Callable[[int, int, float], None] | None = None

    def _classify_retry_reason(self, error: LLMClientError) -> str:
        """Classify the error into a user-friendly retry reason."""
        error_msg = str(error)

        # Rate limiting
        if "429" in error_msg or "rate limit" in error_msg.lower():
            return "API限流(429)，降低并发后重试"

        # Placeholder validation errors
        if "placeholder" in error_msg.lower():
            if "order" in error_msg.lower():
                return "占位符顺序验证失败"
            if "missing" in error_msg.lower() or "changed" in error_msg.lower():
                return "占位符完整性验证失败"
            return "占位符验证失败"

        # Residual language errors
        if any(pattern in error_msg for pattern in ["excessive English", "excessive Chinese", "残留"]):
            return "残留语言检测失败"

        # Network/timeout errors
        if any(keyword in error_msg.lower() for keyword in ["timeout", "connection", "network"]):
            return "网络超时或连接失败"

        # API errors
        if "500" in error_msg or "502" in error_msg or "503" in error_msg:
            return "API服务端错误"

        # Generic fallback
        return f"翻译失败: {error_msg[:100]}"

    def _estimate_remaining_time(self) -> float:
        """Estimate remaining time in seconds based on historical batch times."""
        if not self._batch_times or self._completed_segments >= self._total_segments:
            return 0.0

        # Calculate average time per segment from recent batches
        recent_batches = self._batch_times[-5:]  # Use last 5 batches for better accuracy
        total_time = sum(recent_batches)
        total_segments_in_batches = len(recent_batches) * self.batch_size

        if total_segments_in_batches == 0:
            return 0.0

        avg_time_per_segment = total_time / total_segments_in_batches
        remaining_segments = self._total_segments - self._completed_segments

        return avg_time_per_segment * remaining_segments

    def _resolve_validation_settings(
        self,
        settings,
    ) -> tuple[int, bool, int]:
        """Resolve effective validation settings from mode plus optional overrides.

        When callers only switch ``validation_mode`` and leave the per-setting values
        at balanced defaults, treat them as implicit and apply the selected preset.
        """
        balanced_defaults = self._VALIDATION_MODE_PRESETS["balanced"]
        preset = self._VALIDATION_MODE_PRESETS.get(
            settings.validation_mode,
            balanced_defaults,
        )

        residual_language_threshold = settings.residual_language_threshold
        allow_placeholder_reorder = settings.allow_placeholder_reorder
        min_batch_split_size = settings.min_batch_split_size

        if settings.validation_mode != "balanced":
            if residual_language_threshold == balanced_defaults[0]:
                residual_language_threshold = preset[0]
            if allow_placeholder_reorder == balanced_defaults[1]:
                allow_placeholder_reorder = preset[1]
            if min_batch_split_size == balanced_defaults[2]:
                min_batch_split_size = preset[2]

        return (
            residual_language_threshold,
            allow_placeholder_reorder,
            min_batch_split_size,
        )

    def _detect_document_type(self, segments) -> str:
        """Detect document type based on content patterns."""
        if not segments:
            return "general"

        # Sample first 20 segments for analysis
        sample_size = min(20, len(segments))
        sample_texts = [seg.text for seg in segments[:sample_size]]
        combined_text = " ".join(sample_texts)

        # Count technical indicators
        code_blocks = combined_text.count("```")
        technical_terms = len(re.findall(r"\b[a-z_]+_[a-z_]+\b", combined_text))
        camel_case = len(re.findall(r"\b[a-z]+[A-Z][a-zA-Z]*\b", combined_text))

        # Technical document if high density of code/technical terms
        if code_blocks > 2 or technical_terms > 10 or camel_case > 5:
            return "technical"

        return "general"

    def _record_retry_attempt(self) -> None:
        with self._metrics_lock:
            self._retry_attempts += 1

    def _record_rate_limit_backoff(self) -> None:
        with self._metrics_lock:
            self._rate_limit_backoff_count += 1

    def _record_split_batch_fallback(self) -> None:
        with self._metrics_lock:
            self._split_batch_fallback_count += 1

    def _record_single_segment_placeholder_fallback(self) -> None:
        with self._metrics_lock:
            self._single_segment_placeholder_fallback_count += 1

    def _is_rate_limit_error(self, error: LLMClientError) -> bool:
        message = str(error).upper()
        return (
            "429" in message
            or "TOO MANY REQUESTS" in message
            or "RATE LIMITED" in message
            or "THROTTL" in message
        )

    def _normalize_placeholder_tokens(self, text: str) -> str:
        unescaped_text = self._PLACEHOLDER_ESCAPED_AT_RE.sub("@", text)
        return self._PLACEHOLDER_LOOSE_RE.sub(
            lambda match: f"@@PROTECT_{int(match.group(1)):04d}@@",
            unescaped_text,
        )

    def _validate_placeholders(self, source_text: str, source_placeholders: list[str], translated_placeholders: list[str]) -> bool:
        """Validate placeholder consistency between source and translation."""
        # First check: must have same placeholders (as sets)
        if set(source_placeholders) != set(translated_placeholders):
            return False

        # If reordering is allowed, we're done
        if getattr(self, 'allow_placeholder_reorder', True):
            # Check for directional keywords that require order preservation
            if self._DIRECTIONAL_KEYWORDS_RE.search(source_text):
                # Directional context detected, require exact order
                return source_placeholders == translated_placeholders
            # No directional keywords, allow reordering
            return True

        # Strict mode: require exact order
        return source_placeholders == translated_placeholders
