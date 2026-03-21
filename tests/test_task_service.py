from __future__ import annotations

from dataclasses import dataclass
import re
import threading

import pytest

from doc_translation_tool.config import LLMSettings
from doc_translation_tool.llm import BaseLLMClient, LLMClientError, TranslationResult
from doc_translation_tool.markdown import MarkdownParser, MarkdownProtector, MarkdownSegmenter
from doc_translation_tool.services import TranslationTaskService


@dataclass(slots=True)
class FakeBatchClient(BaseLLMClient):
    settings: LLMSettings
    fail_once_on_batch_index: int | None = None

    def __post_init__(self) -> None:
        self.calls: list[list[str]] = []
        self._batch_counter = 0
        self._failed_batches: set[int] = set()

    def check_connection(self) -> str:
        return "OK"

    def translate_batch(self, items, direction: str, glossary=None):
        self.calls.append([item.id for item in items])
        current_batch_index = self._batch_counter
        self._batch_counter += 1

        if (
            self.fail_once_on_batch_index is not None
            and current_batch_index == self.fail_once_on_batch_index
            and current_batch_index not in self._failed_batches
        ):
            self._failed_batches.add(current_batch_index)
            raise LLMClientError("temporary batch failure")

        suffix = "EN" if direction == "zh_to_en" else "ZH"
        return [
            TranslationResult(
                id=item.id,
                translated_text=self._build_translated_text(item.text, suffix=suffix),
            )
            for item in items
        ]

    def close(self) -> None:
        return None

    def _build_translated_text(self, text: str, *, suffix: str) -> str:
        translated = f"[{suffix}] {text}"
        if suffix == "EN" and "@@PROTECT_" in text:
            translated = re.sub(r"[\u4e00-\u9fff]+", "translated", translated)
            translated = translated.replace("，", ", ").replace("。", ".")
        return translated


def _build_segmented_document(text: str, *, max_segment_length: int = 20):
    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=max_segment_length)
    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)
    return segmented


def _build_client(*, fail_once_on_batch_index: int | None = None) -> FakeBatchClient:
    return FakeBatchClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=2,
            max_retries=1,
        ),
        fail_once_on_batch_index=fail_once_on_batch_index,
    )


def test_translate_segmented_document_batches_segments() -> None:
    segmented = _build_segmented_document(
        "第一句比较短。第二句也比较短。第三句继续说明。第四句补充细节。",
        max_segment_length=12,
    )
    client = _build_client()
    service = TranslationTaskService(client)

    result = service.translate_segmented_document(
        segmented,
        direction="zh_to_en",
    )

    assert result.total_segments == len(segmented.segments)
    assert result.total_batches >= 2
    assert result.successful_batches == result.total_batches
    assert result.retry_attempts == 0
    assert len(result.translated_segment_texts) == len(segmented.segments)
    assert all(text.startswith("[EN] ") for text in result.translated_segment_texts.values())


def test_translate_segmented_document_retries_failed_batch_once() -> None:
    segmented = _build_segmented_document(
        "第一句比较短。第二句也比较短。第三句继续说明。第四句补充细节。",
        max_segment_length=12,
    )
    client = _build_client(fail_once_on_batch_index=1)
    service = TranslationTaskService(client, max_retries=1)

    result = service.translate_segmented_document(
        segmented,
        direction="zh_to_en",
    )

    assert result.successful_batches == result.total_batches
    assert result.retry_attempts == 1
    assert len(client.calls) == result.total_batches + 1


def test_translate_segmented_document_can_run_batches_in_parallel() -> None:
    segmented = _build_segmented_document(
        "第一句比较短。第二句也比较短。第三句继续说明。第四句补充细节。",
        max_segment_length=12,
    )

    class ParallelAwareClient(FakeBatchClient):
        def __post_init__(self) -> None:
            super().__post_init__()
            self._active_calls = 0
            self.max_active_calls = 0
            self._lock = threading.Lock()
            self._barrier = threading.Barrier(2)

        def translate_batch(self, items, direction: str, glossary=None):
            with self._lock:
                self._active_calls += 1
                self.max_active_calls = max(self.max_active_calls, self._active_calls)

            try:
                self._barrier.wait(timeout=1.0)
                return super().translate_batch(items, direction, glossary)
            finally:
                with self._lock:
                    self._active_calls -= 1

    client = ParallelAwareClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=2,
            parallel_batches=2,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, parallel_batches=2)

    result = service.translate_segmented_document(
        segmented,
        direction="zh_to_en",
    )

    assert result.successful_batches == result.total_batches
    assert client.max_active_calls >= 2


def test_translate_segmented_document_raises_after_retry_limit() -> None:
    segmented = _build_segmented_document(
        "第一句比较短。第二句也比较短。第三句继续说明。第四句补充细节。",
        max_segment_length=12,
    )

    class AlwaysFailClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            raise LLMClientError("permanent failure")

    client = AlwaysFailClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=2,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)

    with pytest.raises(LLMClientError, match="batch 1/2 .* after 2 attempts"):
        service.translate_segmented_document(segmented, direction="zh_to_en")


def test_translate_segmented_document_rejects_non_positive_parallel_batches() -> None:
    client = _build_client()

    with pytest.raises(ValueError, match="parallel_batches must be greater than zero"):
        TranslationTaskService(client, parallel_batches=0)


def test_translate_segmented_document_rebuilds_protected_block_texts() -> None:
    segmented = _build_segmented_document(
        "# 标题 `code`\n\n普通段落，包含 [文档](https://example.com/doc)。",
        max_segment_length=100,
    )
    client = _build_client()
    service = TranslationTaskService(client)

    result = service.translate_segmented_document(
        segmented,
        direction="zh_to_en",
    )

    assert len(result.rebuilt_protected_block_texts) == len(segmented.blocks)
    assert "@@PROTECT_" in result.rebuilt_protected_block_texts[0]
    assert "@@PROTECT_" in result.rebuilt_protected_block_texts[-1]
    assert "@@PROTECT_" not in result.final_markdown_text


def test_translate_segmented_document_handles_zero_segments() -> None:
    segmented = _build_segmented_document("```bash\necho hello\n```\n")
    client = _build_client()
    service = TranslationTaskService(client)

    result = service.translate_segmented_document(segmented, direction="zh_to_en")

    assert result.total_segments == 0
    assert result.total_batches == 0
    assert result.rebuilt_protected_block_texts == [block.protected_text for block in segmented.blocks]
    assert result.final_markdown_text == "```bash\necho hello\n```\n"


def test_translate_segmented_document_retries_when_placeholder_sentence_keeps_chinese() -> None:
    segmented = _build_segmented_document(
        "说明 `CONFIG_SPINOR_LOGICAL_OFFSET` 不同，需要根据 `bootpackage` 动态适配。\n",
        max_segment_length=200,
    )

    class ResidualChineseClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            self.calls.append([item.id for item in items])
            current_batch_index = self._batch_counter
            self._batch_counter += 1

            if current_batch_index == 0:
                return [
                    TranslationResult(
                        id=items[0].id,
                        translated_text=(
                            "The sizes of @@PROTECT_0000@@ 不同，需要根据 "
                            "@@PROTECT_0001@@ are dynamically adapted."
                        ),
                    )
                ]

            return [
                TranslationResult(
                    id=items[0].id,
                    translated_text=(
                        "The sizes of @@PROTECT_0000@@ differ and must be "
                        "adjusted dynamically according to @@PROTECT_0001@@."
                    ),
                )
            ]

    client = ResidualChineseClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=1,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)

    result = service.translate_segmented_document(segmented, direction="zh_to_en")

    assert len(client.calls) == 2
    assert "不同" not in result.final_markdown_text
    assert "需要根据" not in result.final_markdown_text
    assert "`CONFIG_SPINOR_LOGICAL_OFFSET`" in result.final_markdown_text
    assert "`bootpackage`" in result.final_markdown_text


def test_translate_segmented_document_retries_when_placeholder_sentence_keeps_english() -> None:
    segmented = _build_segmented_document(
        "The size of `CONFIG_SPINOR_LOGICAL_OFFSET` must be adjusted according to `bootpackage`.\n",
        max_segment_length=200,
    )

    class ResidualEnglishClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            self.calls.append([item.id for item in items])
            current_batch_index = self._batch_counter
            self._batch_counter += 1

            if current_batch_index == 0:
                return [
                    TranslationResult(
                        id=items[0].id,
                        translated_text=(
                            "需要根据 @@PROTECT_0000@@ different and must be adjusted "
                            "according to @@PROTECT_0001@@ 进行处理。"
                        ),
                    )
                ]

            return [
                TranslationResult(
                    id=items[0].id,
                    translated_text=(
                        "需要根据 @@PROTECT_0000@@ 动态调整，并参考 @@PROTECT_0001@@ 进行处理。"
                    ),
                )
            ]

    client = ResidualEnglishClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=1,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)

    result = service.translate_segmented_document(segmented, direction="en_to_zh")

    assert len(client.calls) == 2
    assert "different and must be adjusted according to" not in result.final_markdown_text
    assert "`CONFIG_SPINOR_LOGICAL_OFFSET`" in result.final_markdown_text
    assert "`bootpackage`" in result.final_markdown_text


def test_translate_segmented_document_allows_limited_english_terms_for_en_to_zh() -> None:
    segmented = _build_segmented_document(
        "Check `CONFIG_SPINOR_LOGICAL_OFFSET` against the Linux kernel.\n",
        max_segment_length=200,
    )

    class ProductTermClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            return [
                TranslationResult(
                    id=items[0].id,
                    translated_text="请检查 @@PROTECT_0000@@ 与 Linux kernel 的差异。",
                )
            ]

    client = ProductTermClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=1,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)

    result = service.translate_segmented_document(segmented, direction="en_to_zh")

    assert "Linux kernel" in result.final_markdown_text
    assert "`CONFIG_SPINOR_LOGICAL_OFFSET`" in result.final_markdown_text


def test_translate_segmented_document_retries_when_placeholders_change_order() -> None:
    segmented = _build_segmented_document(
        "| 名称 | 说明 |\n| --- | --- |\n| boot0 | 启动文件 |\n",
        max_segment_length=50,
    )

    class PlaceholderOrderClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            self.calls.append([item.id for item in items])
            current_batch_index = self._batch_counter
            self._batch_counter += 1

            if current_batch_index == 0:
                if len(items) == 2:
                    return [
                        TranslationResult(
                            id=items[0].id,
                            translated_text=(
                                "@@PROTECT_0001@@ Name @@PROTECT_0000@@ "
                                "Description @@PROTECT_0002@@"
                            ),
                        ),
                        TranslationResult(
                            id=items[1].id,
                            translated_text="@@PROTECT_0003@@",
                        ),
                    ]

                return [
                    TranslationResult(
                        id=items[0].id,
                        translated_text=(
                            "@@PROTECT_0004@@ boot0 @@PROTECT_0005@@ "
                            "Boot file @@PROTECT_0006@@"
                        ),
                    )
                ]

            if len(items) == 2:
                return [
                    TranslationResult(
                        id=items[0].id,
                        translated_text=(
                            "@@PROTECT_0000@@ Name @@PROTECT_0001@@ "
                            "Description @@PROTECT_0002@@"
                        ),
                    ),
                    TranslationResult(
                        id=items[1].id,
                        translated_text="@@PROTECT_0003@@",
                    ),
                ]

            return [
                TranslationResult(
                    id=items[0].id,
                    translated_text=(
                        "@@PROTECT_0004@@ boot0 @@PROTECT_0005@@ "
                        "Boot file @@PROTECT_0006@@"
                    ),
                )
            ]

    client = PlaceholderOrderClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=2,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)

    result = service.translate_segmented_document(segmented, direction="zh_to_en")

    assert len(client.calls) == 3
    assert client.calls[0] == client.calls[1]
    assert "| Name | Description |" in result.final_markdown_text


def test_translate_segmented_document_normalizes_placeholder_format_variants() -> None:
    segmented = _build_segmented_document(
        "| 名称 | 说明 |\n| --- | --- |\n",
        max_segment_length=100,
    )

    class PlaceholderFormatClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            self.calls.append([item.id for item in items])
            return [
                TranslationResult(
                    id=items[0].id,
                    translated_text="@@ protect-0 @@ Name @@ protect-1 @@ Description",
                ),
                TranslationResult(
                    id=items[1].id,
                    translated_text="\\@\\@PROTECT_0002\\@\\@",
                ),
            ]

    client = PlaceholderFormatClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=2,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)

    result = service.translate_segmented_document(segmented, direction="zh_to_en")

    assert len(client.calls) == 1
    assert "| Name | Description |" in result.final_markdown_text
    assert "| --- | --- |" in result.final_markdown_text


def test_translate_segmented_document_logs_retry_context() -> None:
    segmented = _build_segmented_document(
        "第一句比较短。第二句也比较短。第三句继续说明。第四句补充细节。",
        max_segment_length=12,
    )
    client = _build_client(fail_once_on_batch_index=0)
    service = TranslationTaskService(client, max_retries=1)
    logs: list[str] = []

    result = service.translate_segmented_document(
        segmented,
        direction="zh_to_en",
        on_log=logs.append,
    )

    assert result.successful_batches == result.total_batches
    assert any("开始批次 1/" in message for message in logs)
    assert any("第 1 次失败，准备重试" in message for message in logs)
    assert any("重试成功" in message for message in logs)
    assert any("seg-0000" in message for message in logs)


def test_translate_segmented_document_failure_mentions_batch_and_segments() -> None:
    segmented = _build_segmented_document(
        "第一句比较短。第二句也比较短。第三句继续说明。",
        max_segment_length=12,
    )

    class AlwaysFailClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            raise LLMClientError("permanent failure")

    client = AlwaysFailClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=2,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)

    with pytest.raises(LLMClientError) as exc_info:
        service.translate_segmented_document(
            segmented,
            direction="zh_to_en",
        )

    assert "batch 1/" in str(exc_info.value)
    assert "segments: seg-0000" in str(exc_info.value)


def test_translate_segmented_document_splits_failed_batch_for_placeholder_order_error() -> None:
    segmented = _build_segmented_document(
        "| 名称 | 说明 |\n| --- | --- |\n| boot0 | 启动文件 |\n| env | 环境变量 |\n",
        max_segment_length=150,
    )

    class SplitFallbackClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            self.calls.append([item.id for item in items])
            if len(items) > 1:
                return [
                    TranslationResult(
                        id=item.id,
                        translated_text=item.text.replace(
                            "@@PROTECT_0000@@",
                            "@@PROTECT_9999@@",
                        ),
                    )
                    for item in items
                ]

            text = items[0].text
            replacements = {
                "名称": "Name",
                "说明": "Description",
                "启动文件": "Boot file",
                "环境变量": "Environment variable",
            }
            for source, target in replacements.items():
                text = text.replace(source, target)
            return [TranslationResult(id=items[0].id, translated_text=text)]

    client = SplitFallbackClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=8,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)
    logs: list[str] = []

    result = service.translate_segmented_document(
        segmented,
        direction="zh_to_en",
        on_log=logs.append,
    )

    assert any("降批" in message for message in logs)
    assert any(len(call) > 1 for call in client.calls)
    assert any(len(call) == 1 for call in client.calls)
    assert "| Name | Description |" in result.final_markdown_text
    assert "| boot0 | Boot file |" in result.final_markdown_text


def test_translate_segmented_document_does_not_split_single_segment_failure() -> None:
    segmented = _build_segmented_document(
        "| 名称 | 说明 |\n| --- | --- |\n",
        max_segment_length=200,
    )

    class SingleSegmentOrderFailClient(FakeBatchClient):
        def translate_batch(self, items, direction: str, glossary=None):
            self.calls.append([item.id for item in items])
            return [
                TranslationResult(
                    id=items[0].id,
                    translated_text=items[0].text.replace(
                        "@@PROTECT_0000@@",
                        "@@PROTECT_9999@@",
                    ),
                )
            ]

    client = SingleSegmentOrderFailClient(
        settings=LLMSettings(
            provider="openai_compatible",
            api_format="openai",
            base_url="https://llm.example/v1",
            api_key="secret",
            model="test-model",
            batch_size=8,
            max_retries=1,
        )
    )
    service = TranslationTaskService(client, max_retries=1)

    with pytest.raises(LLMClientError, match="after 2 attempts"):
        service.translate_segmented_document(segmented, direction="zh_to_en")
