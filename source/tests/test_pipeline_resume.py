from __future__ import annotations

from pathlib import Path
import re
import shutil
import uuid

from doc_translation_tool.config import AppSettings, LLMSettings
from doc_translation_tool.llm import BaseLLMClient, TranslationResult
from doc_translation_tool.markdown import MarkdownParser, MarkdownProtector, MarkdownSegmenter
from doc_translation_tool.models import TranslationTask
from doc_translation_tool.services.pipeline import DocumentTranslationPipeline
from doc_translation_tool.services.translation_cache import (
    TranslationCheckpoint,
    TranslationCheckpointCache,
)


class ResumePipelineClient(BaseLLMClient):
    def __init__(self, settings: LLMSettings) -> None:
        super().__init__(settings)
        self.calls: list[list[str]] = []
        self.closed = False

    def check_connection(self) -> str:
        return "OK"

    def translate_batch(self, items, direction: str, glossary=None):
        self.calls.append([item.id for item in items])
        return [
            TranslationResult(
                id=item.id,
                translated_text="[EN] "
                + re.sub(r"[\u4e00-\u9fff]+", "translated", item.text).replace("。", "."),
            )
            for item in items
        ]

    def close(self) -> None:
        self.closed = True


def _make_test_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".tmp" / f"pipeline-resume-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_pipeline_resumes_from_cached_segments_and_clears_checkpoint() -> None:
    temp_dir = _make_test_dir()
    try:
        root = Path(temp_dir)
        project_root = root / "project"
        project_root.mkdir()
        output_dir = root / "out"
        output_dir.mkdir()
        source_file = root / "guide.md"
        source_file.write_text(
            "第一句比较短。第二句也比较短。第三句继续说明。第四句补充细节。\n",
            encoding="utf-8",
        )

        settings = AppSettings(
            project_root=str(project_root),
            llm=LLMSettings(
                provider="openai_compatible",
                api_format="openai",
                base_url="https://llm.example/v1",
                api_key="secret",
                model="test-model",
                batch_size=2,
                max_retries=0,
            ),
        )
        client = ResumePipelineClient(settings.llm)
        cache = TranslationCheckpointCache()

        parser = MarkdownParser()
        protector = MarkdownProtector()
        segmenter = MarkdownSegmenter(max_segment_length=12)
        segmented_document = segmenter.segment(
            protector.protect(parser.parse(source_file.read_text(encoding="utf-8")))
        )
        cache_path = cache.build_cache_path(
            source_path=source_file,
            output_dir=output_dir,
            direction="zh_to_en",
        )
        cache.save(
            cache_path,
            TranslationCheckpoint(
                source_path=str(source_file),
                direction="zh_to_en",
                document_fingerprint=cache.build_document_fingerprint(segmented_document),
                translated_segment_texts={
                    segmented_document.segments[0].id: "[EN] cached first segment"
                },
            ),
        )

        pipeline = DocumentTranslationPipeline(
            project_root=project_root,
            settings_loader=lambda _root: settings,
            client_factory=lambda _settings: client,
            segmenter=MarkdownSegmenter(max_segment_length=12),
            checkpoint_cache=cache,
        )

        result = pipeline.execute(
            TranslationTask(
                source_path=str(source_file),
                output_dir=str(output_dir),
                direction="zh_to_en",
            )
        )

        assert client.closed is True
        assert len(client.calls) == 2
        assert all(segmented_document.segments[0].id not in batch for batch in client.calls)
        assert result.reused_cached_segments == 1
        assert Path(result.output_path).exists() is True
        assert cache_path.exists() is False
        assert cache_path.parent.exists() is False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
