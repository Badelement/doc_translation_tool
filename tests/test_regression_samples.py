from __future__ import annotations

import json
from pathlib import Path

from doc_translation_tool.config import AppSettings, LLMSettings
from doc_translation_tool.llm import BaseLLMClient, TranslationResult
from doc_translation_tool.markdown import (
    MarkdownParser,
    MarkdownProtector,
    MarkdownRebuilder,
    MarkdownSegmenter,
)
from doc_translation_tool.models import TranslationTask
from doc_translation_tool.services import DocumentTranslationPipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "regression"


class FakeRegressionClient(BaseLLMClient):
    def __init__(self, settings: LLMSettings) -> None:
        super().__init__(settings)
        self.glossary_calls: list[list[dict[str, str]] | None] = []

    def check_connection(self) -> str:
        return "OK"

    def translate_batch(self, items, direction: str, glossary=None):
        self.glossary_calls.append(glossary)
        glossary = glossary or []
        results: list[TranslationResult] = []

        replacements = [
            ("用于验证回归样例。", "Used to verify regression samples."),
            ("参数", "The value of "),
            ("需要和", " must stay aligned with "),
            ("保持一致。", "."),
            ("使用 ", "Before using "),
            (" 前，请确认 ", ", please confirm that "),
            (" 配置正确。", " is configured correctly."),
            ("请查看 ", "Please see "),
            (" 和 ", " and "),
            ("。", "."),
            ("烧录说明", "Flashing Guide"),
            ("用户手册", "User Guide"),
            ("流程图", "Flowchart"),
            ("示例文档", "Sample Document"),
            ("启动说明", "Startup Guide"),
            ("名称", "Name"),
            ("说明", "Description"),
        ]

        for item in items:
            text = item.text

            for entry in glossary:
                text = text.replace(entry["source"], entry["target"])

            for source, target in replacements:
                text = text.replace(source, target)

            results.append(TranslationResult(id=item.id, translated_text=text))

        return results

    def close(self) -> None:
        return None


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _build_settings(project_root: Path) -> AppSettings:
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
    )


def test_regression_sample_roundtrip_restores_original_markdown() -> None:
    text = _read_fixture("sample_zh.md")

    parser = MarkdownParser()
    protector = MarkdownProtector()
    segmenter = MarkdownSegmenter(max_segment_length=80)
    rebuilder = MarkdownRebuilder()

    protected = protector.protect(parser.parse(text))
    segmented = segmenter.segment(protected)

    assert rebuilder.rebuild_document(segmented) == text


def test_regression_sample_pipeline_matches_expected_output(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "sample_zh.md"
    source_file.write_text(_read_fixture("sample_zh.md"), encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    glossary = [
        {"source": "启动文件", "target": "Boot file"},
        {"source": "环境变量", "target": "Environment variable"},
    ]
    (project_root / "glossary.json").write_text(
        json.dumps(glossary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    client = FakeRegressionClient(_build_settings(project_root).llm)
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
        )
    )

    assert Path(result.output_path).read_text(encoding="utf-8") == _read_fixture(
        "sample_expected_en.md"
    )
    assert client.glossary_calls
    assert client.glossary_calls[0] == glossary
