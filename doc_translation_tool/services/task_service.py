from __future__ import annotations

from concurrent.futures import FIRST_EXCEPTION, ThreadPoolExecutor, wait
import re
import threading
from dataclasses import dataclass, field
from time import perf_counter
from typing import Callable

from doc_translation_tool.llm import BaseLLMClient, LLMClientError, TranslationItem
from doc_translation_tool.markdown import MarkdownRebuilder, SegmentedMarkdownDocument


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
    batch_errors: list[str] = field(default_factory=list)


class TranslationTaskService:
    """Batch translation orchestration on top of the LLM client."""

    _PLACEHOLDER_RE = re.compile(r"@@PROTECT_\d+@@")
    _PLACEHOLDER_ESCAPED_AT_RE = re.compile(r"\\@")
    _PLACEHOLDER_LOOSE_RE = re.compile(
        r"@@\s*protect\s*[_-]\s*(\d+)\s*@@",
        flags=re.IGNORECASE,
    )
    _ZH_CHAR_RE = re.compile(r"[\u4e00-\u9fff]")
    _EN_WORD_RE = re.compile(r"\b[A-Za-z][A-Za-z0-9_-]*\b")
    _SPLITTABLE_ERROR_PATTERNS = (
        "Translated text changed protected placeholder tokens or their order.",
        "Translated text still contains Chinese outside protected placeholders.",
        "Translated text still contains too much English outside protected placeholders.",
        "Translated item IDs do not match the request order.",
    )

    def __init__(
        self,
        client: BaseLLMClient,
        *,
        batch_size: int | None = None,
        parallel_batches: int | None = None,
        max_retries: int | None = None,
    ) -> None:
        self.client = client
        self.rebuilder = MarkdownRebuilder()
        self.batch_size = batch_size or client.settings.batch_size
        self.parallel_batches = (
            parallel_batches
            if parallel_batches is not None
            else client.settings.parallel_batches
        )
        self.max_retries = (
            max_retries if max_retries is not None else client.settings.max_retries
        )

        if self.batch_size <= 0:
            raise ValueError("batch_size must be greater than zero.")
        if self.parallel_batches <= 0:
            raise ValueError("parallel_batches must be greater than zero.")
        if self.max_retries < 0:
            raise ValueError("max_retries must be zero or greater.")
        self._metrics_lock = threading.Lock()
        self._retry_attempts = 0

    def translate_segmented_document(
        self,
        document: SegmentedMarkdownDocument,
        *,
        direction: str,
        glossary: list[dict[str, str]] | None = None,
        on_batch_complete: Callable[[int, int], None] | None = None,
        on_batch_started: Callable[[int, int, int], None] | None = None,
        on_log: Callable[[str], None] | None = None,
    ) -> BatchTranslationResult:
        segments = document.segments
        total_batches = self._count_batches(len(segments))
        translated_segment_texts: dict[str, str] = {}
        successful_batches = 0
        batch_errors: list[str] = []
        self._retry_attempts = 0

        if not segments:
            if on_log is not None:
                on_log("[翻译] 没有可翻译片段，直接回填输出。")
            rebuilt_blocks = self.rebuild_protected_block_texts(
                document,
                translated_segment_texts,
            )
            final_markdown_text = self.rebuild_markdown_text(
                document,
                translated_segment_texts,
            )
            return BatchTranslationResult(
                translated_segment_texts=translated_segment_texts,
                rebuilt_protected_block_texts=rebuilt_blocks,
                final_markdown_text=final_markdown_text,
                total_segments=0,
                total_batches=0,
                successful_batches=0,
                retry_attempts=0,
                batch_errors=[],
            )

        indexed_batches = list(enumerate(self._iter_batches(segments), start=1))

        if self.parallel_batches == 1 or total_batches <= 1:
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
                for item in batch_result:
                    translated_segment_texts[item.id] = item.translated_text

                successful_batches += 1
                if on_batch_complete is not None:
                    on_batch_complete(successful_batches, total_batches)
        else:
            max_workers = min(self.parallel_batches, total_batches)
            with ThreadPoolExecutor(
                max_workers=max_workers,
                thread_name_prefix="doc-translate-batch",
            ) as executor:
                pending = {
                    executor.submit(
                        self._run_single_batch,
                        batch,
                        direction=direction,
                        glossary=glossary,
                        batch_index=batch_index,
                        total_batches=total_batches,
                        on_log=on_log,
                    )
                    for batch_index, batch in indexed_batches
                }

                if on_batch_started is not None:
                    for batch_index, _batch in indexed_batches:
                        on_batch_started(batch_index, total_batches, successful_batches)

                while pending:
                    done, pending = wait(
                        pending,
                        return_when=FIRST_EXCEPTION,
                    )

                    for future in done:
                        try:
                            batch_result = future.result()
                        except LLMClientError as exc:
                            batch_errors.append(str(exc))
                            for pending_future in pending:
                                pending_future.cancel()
                            raise

                        for item in batch_result:
                            translated_segment_texts[item.id] = item.translated_text

                        successful_batches += 1
                        if on_batch_complete is not None:
                            on_batch_complete(successful_batches, total_batches)

        rebuilt_blocks = self.rebuild_protected_block_texts(
            document,
            translated_segment_texts,
        )
        final_markdown_text = self.rebuild_markdown_text(
            document,
            translated_segment_texts,
        )
        return BatchTranslationResult(
            translated_segment_texts=translated_segment_texts,
            rebuilt_protected_block_texts=rebuilt_blocks,
            final_markdown_text=final_markdown_text,
            total_segments=len(segments),
            total_batches=total_batches,
            successful_batches=successful_batches,
            retry_attempts=self._retry_attempts,
            batch_errors=batch_errors,
        )

    def rebuild_protected_block_texts(
        self,
        document: SegmentedMarkdownDocument,
        translated_segment_texts: dict[str, str],
    ) -> list[str]:
        return self.rebuilder.rebuild_protected_block_texts(
            document,
            translated_segment_texts,
        )

    def rebuild_markdown_text(
        self,
        document: SegmentedMarkdownDocument,
        translated_segment_texts: dict[str, str],
    ) -> str:
        return self.rebuilder.rebuild_document(
            document,
            translated_segment_texts,
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
        batch_ids = ", ".join(segment.id for segment in batch)
        if on_log is not None:
            on_log(
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
        if on_log is not None:
            on_log(
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
        last_error: LLMClientError | None = None
        batch_ids = ", ".join(segment.id for segment in batch)

        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self._record_retry_attempt()
            if on_log is not None:
                on_log(
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
                if on_log is not None and attempt > 0:
                    on_log(
                        f"[重试] 批次 {batch_index}/{total_batches} 重试成功，"
                        f"片段：{batch_ids}"
                    )
                return result
            except LLMClientError as exc:
                last_error = exc
                if on_log is not None:
                    if attempt < self.max_retries:
                        on_log(
                            f"[重试] 批次 {batch_index}/{total_batches} 第 {attempt + 1} 次失败，"
                            f"准备重试。片段：{batch_ids}。原因：{exc}"
                        )
                    else:
                        on_log(
                            f"[失败] 批次 {batch_index}/{total_batches} 最终失败。"
                            f"片段：{batch_ids}。原因：{exc}"
                        )
                if attempt == self.max_retries:
                    break

        assert last_error is not None
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
            if len(batch) <= 1 or not self._should_split_failed_batch(exc):
                raise

            midpoint = len(batch) // 2
            left_batch = batch[:midpoint]
            right_batch = batch[midpoint:]

            if on_log is not None:
                on_log(
                    f"[降批] 批次 {batch_index}/{total_batches} 因结构校验失败，"
                    f"拆分为 {len(left_batch)} + {len(right_batch)} 个片段继续重试。"
                )
                on_log(
                    "[降批] 左侧片段："
                    + ", ".join(segment.id for segment in left_batch)
                )
                on_log(
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
            if translated_placeholders != source_placeholders:
                raise LLMClientError(
                    "Translated text changed protected placeholder tokens or their order."
                )
            item.translated_text = normalized_translated_text

            if not self._PLACEHOLDER_RE.search(source_text):
                continue

            translated_without_placeholders = self._PLACEHOLDER_RE.sub(
                " ",
                normalized_translated_text,
            )
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
        return len(lowercase_words) >= 3

    def _record_retry_attempt(self) -> None:
        with self._metrics_lock:
            self._retry_attempts += 1

    def _normalize_placeholder_tokens(self, text: str) -> str:
        unescaped_text = self._PLACEHOLDER_ESCAPED_AT_RE.sub("@", text)
        return self._PLACEHOLDER_LOOSE_RE.sub(
            lambda match: f"@@PROTECT_{int(match.group(1)):04d}@@",
            unescaped_text,
        )
