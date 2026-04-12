from __future__ import annotations

from pathlib import Path

from doc_translation_tool.config import AppSettings, LLMSettings
from doc_translation_tool.documents import DitaDocumentHandler
from doc_translation_tool.llm import BaseLLMClient, TranslationResult
from doc_translation_tool.models import TranslationTask
from doc_translation_tool.services import DocumentTranslationPipeline


FIXTURE_DIR = Path(__file__).parent / "fixtures" / "dita"


class FakeDitaRegressionClient(BaseLLMClient):
    def __init__(self, settings: LLMSettings) -> None:
        super().__init__(settings)

    def check_connection(self) -> str:
        return "OK"

    def translate_batch(self, items, direction: str, glossary=None):
        del direction, glossary
        replacements = [
            ("用于验证 DITA 回归样例。", "Used to verify DITA regression samples."),
            ("参数 ", "The value of "),
            (" 需要和 ", " must stay aligned with "),
            (" 保持一致。", "."),
            ("使用 ", "Before using "),
            (" 前，请确认 ", ", please confirm that "),
            (" 配置正确。", " is configured correctly."),
            ("完成后，请查看 ", "After completion, please review "),
            ("请查看", "Please see "),
            ("用户手册", "User Guide"),
            ("启动说明", "Startup Guide"),
            ("配置说明", "Configuration Guide"),
            ("复杂流程说明", "Complex Flow Guide"),
            ("设备初始化流程", "Device Initialization Flow"),
            ("准备阶段", "Preparation"),
            ("请检查 ", "Please check "),
            ("请先检查 ", "Please check "),
            (" 和 ", " and "),
            ("如果", "If the "),
            ("缺失，请执行 ", " is missing, please run "),
            (" 缺失，请执行 ", " is missing, please run "),
            ("启动文档", "Boot Document"),
            ("开始前，请确认 ", "Before starting, please confirm that "),
            (" 已准备完成。", " are ready."),
            ("打开设置页面。", "Open the settings page."),
            ("如果配置说明不可用，请联系维护人员。", "If the Configuration Guide is unavailable, please contact the maintainer."),
            ("不可用，请联系维护人员。", " is unavailable, please contact the maintainer."),
            ("界面会提示 ", "The screen shows "),
            ("，并显示 ", " and "),
            ("选择启动模式。", "Select the startup mode."),
            ("标准模式。", "Standard mode."),
            ("安全模式。", "Safe mode."),
            ("系统会生成 ", "The system generates "),
            ("打开控制台。", "Open the console."),
            ("界面会显示 ", "The screen shows "),
            ("启动文件", "Boot file"),
            ("名称", "Name"),
            ("说明", "Description"),
            ("。", "."),
        ]

        results: list[TranslationResult] = []
        for item in items:
            text = item.text
            for source, target in replacements:
                text = text.replace(source, target)
            results.append(TranslationResult(id=item.id, translated_text=text))
        return results

    def close(self) -> None:
        return None


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


def _read_fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_dita_regression_sample_roundtrip_restores_original_document(
    tmp_path: Path,
) -> None:
    handler = DitaDocumentHandler()
    source_text = _read_fixture("sample_zh.dita")

    prepared = handler.prepare_document(
        source_text,
        settings=_build_settings(tmp_path),
    )

    assert handler.rebuild_document(prepared) == source_text


def test_dita_regression_sample_pipeline_matches_expected_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "sample_zh.dita"
    source_file.write_text(_read_fixture("sample_zh.dita"), encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    client = FakeDitaRegressionClient(_build_settings(project_root).llm)
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
        "sample_expected_en.dita"
    )


def test_dita_complex_regression_sample_pipeline_matches_expected_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "sample_complex_zh.dita"
    source_file.write_text(_read_fixture("sample_complex_zh.dita"), encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    client = FakeDitaRegressionClient(_build_settings(project_root).llm)
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
        "sample_complex_expected_en.dita"
    )


def test_dita_task_regression_sample_pipeline_matches_expected_output(
    tmp_path: Path,
) -> None:
    project_root = tmp_path / "project"
    project_root.mkdir()
    source_file = tmp_path / "sample_task_zh.dita"
    source_file.write_text(_read_fixture("sample_task_zh.dita"), encoding="utf-8")
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    client = FakeDitaRegressionClient(_build_settings(project_root).llm)
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
        "sample_task_expected_en.dita"
    )
