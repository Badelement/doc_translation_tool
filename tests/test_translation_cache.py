from __future__ import annotations

from pathlib import Path
import shutil
import uuid

from doc_translation_tool.markdown import MarkdownParser, MarkdownProtector, MarkdownSegmenter
from doc_translation_tool.services.translation_cache import (
    TranslationCheckpoint,
    TranslationCheckpointCache,
)


def _build_segmented_document(text: str):
    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=20)
    return segmenter.segment(protector.protect(parser.parse(text)))


def _make_test_dir() -> Path:
    path = Path(__file__).resolve().parents[1] / ".tmp" / f"cache-test-{uuid.uuid4().hex}"
    path.mkdir(parents=True, exist_ok=True)
    return path


def test_translation_checkpoint_cache_roundtrip_and_fingerprint_guard() -> None:
    cache = TranslationCheckpointCache()
    document = _build_segmented_document("第一句。第二句。第三句。")
    fingerprint = cache.build_document_fingerprint(document)

    temp_dir = _make_test_dir()
    try:
        cache_path = cache.build_cache_path(
            source_path="guide.md",
            output_dir=temp_dir,
            direction="zh_to_en",
        )
        checkpoint = TranslationCheckpoint(
            source_path="guide.md",
            direction="zh_to_en",
            document_fingerprint=fingerprint,
            translated_segment_texts={document.segments[0].id: "cached"},
        )

        cache.save(cache_path, checkpoint)

        loaded = cache.load(
            cache_path,
            source_path="guide.md",
            direction="zh_to_en",
            document_fingerprint=fingerprint,
        )
        mismatched = cache.load(
            cache_path,
            source_path="guide.md",
            direction="zh_to_en",
            document_fingerprint="different",
        )

        assert loaded == {document.segments[0].id: "cached"}
        assert mismatched == {}

        cache.clear(cache_path)
        assert Path(cache_path).exists() is False
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
