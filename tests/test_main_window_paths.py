import re
from pathlib import Path

from pytest import MonkeyPatch
from PySide6.QtWidgets import QDialog

from doc_translation_tool import __version__
from doc_translation_tool.services import TranslationPipelineResult
from doc_translation_tool.ui.main_window import MainWindow


def test_main_window_shows_incomplete_model_config_status_on_startup(
    tmp_path: Path,
    qapp,
) -> None:
    window = MainWindow(project_root=tmp_path)

    assert window.connection_hint_label.text() == "模型状态：配置不完整"
    assert "base_url" in window.connection_hint_label.toolTip()
    assert "api_key" in window.connection_hint_label.toolTip()
    assert "model" in window.connection_hint_label.toolTip()
    window.close()
    window.deleteLater()


def test_main_window_shows_loaded_model_config_status_on_startup(
    tmp_path: Path,
    qapp,
) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "DOC_TRANS_BASE_URL=https://example.com/v1",
                "DOC_TRANS_API_KEY=test-key",
                "DOC_TRANS_MODEL=test-model",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    window = MainWindow(project_root=tmp_path)

    assert window.connection_hint_label.text() == "模型状态：配置已加载，待检查连通性"
    assert "实际连通性会在开始翻译时检查" in window.connection_hint_label.toolTip()
    window.close()
    window.deleteLater()


def test_main_window_shows_config_load_failure_on_startup(
    tmp_path: Path,
    qapp,
) -> None:
    (tmp_path / "settings.json").write_text("{bad json", encoding="utf-8")

    window = MainWindow(project_root=tmp_path)

    assert window.connection_hint_label.text() == "模型状态：配置加载失败"
    assert "读取配置失败" in window.connection_hint_label.toolTip()
    window.close()
    window.deleteLater()


def test_start_translation_task_updates_model_status_to_connectivity_checking(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "demo.md"
    source_file.write_text("# demo\n", encoding="utf-8")

    window = MainWindow(project_root=tmp_path)

    class FakeSignal:
        def connect(self, _callback) -> None:
            return None

    class FakeWorker:
        def __init__(self) -> None:
            self.progress_updated = FakeSignal()
            self.log_message = FakeSignal()
            self.connection_checked = FakeSignal()
            self.translation_succeeded = FakeSignal()
            self.translation_failed = FakeSignal()
            self.finished = FakeSignal()

        def start(self) -> None:
            return None

        def isRunning(self) -> bool:
            return False

    window._worker = None
    window._build_translation_worker = lambda _task: FakeWorker()

    window._start_translation_task(
        source_path=str(source_file),
        output_dir=str(tmp_path),
        direction="zh_to_en",
    )

    assert window.connection_hint_label.text() == "模型状态：正在检查接口连通性"
    assert "正在验证当前配置" in window.connection_hint_label.toolTip()
    window.close()
    window.deleteLater()


def test_handle_connection_checked_updates_model_status_to_connected(qapp) -> None:
    window = MainWindow()

    window._handle_connection_checked("OK")

    assert window.connection_hint_label.text() == "模型状态：接口连通 (OK)"
    assert "接口连通性检查" in window.connection_hint_label.toolTip()
    window.close()
    window.deleteLater()


def test_set_source_path_updates_source_and_output_dir(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "demo.md"
    source_file.write_text("# demo\n", encoding="utf-8")

    window = MainWindow()
    assert window.windowTitle().endswith(f"v{__version__}")
    window.set_source_path(str(source_file))

    assert window.source_path_edit.text() == str(source_file)
    assert window.output_dir_edit.text() == str(tmp_path)
    window.close()
    window.deleteLater()


def test_handle_translation_failed_429_shows_rate_limit_suggestion(
    monkeypatch: MonkeyPatch,
    qapp,
) -> None:
    captured: dict[str, str] = {}

    def fake_critical(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.critical",
        fake_critical,
    )

    window = MainWindow()
    window._handle_translation_failed(
        "check_connection",
        "模型连接失败：Model request rate limited: HTTP 429 Too Many Requests.",
    )

    assert captured["title"] == "模型连接失败"
    assert "429" in captured["message"]
    assert "限流" in captured["message"]
    window.close()
    window.deleteLater()


def test_set_output_directory_updates_output_edit(tmp_path: Path, qapp) -> None:
    window = MainWindow()
    window.set_output_directory(str(tmp_path))

    assert window.output_dir_edit.text() == str(tmp_path)
    window.close()
    window.deleteLater()


def test_commit_source_path_text_updates_source_and_output_dir(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "paste-demo.md"
    source_file.write_text("# pasted\n", encoding="utf-8")

    window = MainWindow()
    window.source_path_edit.setText(str(source_file))
    window._commit_source_path_text()

    assert window.source_path_edit.text() == str(source_file)
    assert window.output_dir_edit.text() == str(tmp_path)
    window.close()
    window.deleteLater()


def test_handle_source_path_received_auto_switches_direction_without_warning(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "english.md"
    source_file.write_text(
        "This document explains the camera driver architecture in English.\n",
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow()
    window.handle_source_path_received(str(source_file))

    assert captured == {}
    assert window.en_to_zh_radio.isChecked() is True
    window.close()
    window.deleteLater()


def test_handle_source_path_received_auto_switches_to_en_to_zh_for_english_file(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "english.md"
    source_file.write_text(
        "This document explains the camera driver architecture in English.\n",
        encoding="utf-8",
    )

    window = MainWindow()
    window.handle_source_path_received(str(source_file))

    assert window.en_to_zh_radio.isChecked() is True
    window.close()
    window.deleteLater()


def test_handle_source_path_received_auto_switches_to_zh_to_en_for_chinese_file(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "chinese.md"
    source_file.write_text(
        "本文档用于说明相机驱动架构和启动流程。\n",
        encoding="utf-8",
    )

    window = MainWindow()
    window.en_to_zh_radio.setChecked(True)
    window.handle_source_path_received(str(source_file))

    assert window.zh_to_en_radio.isChecked() is True
    window.close()
    window.deleteLater()


def test_handle_source_path_received_auto_switches_for_chinese_dita_file(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "chinese.dita"
    source_file.write_text(
        "<topic id='demo'><title>标题</title><body><p>本文档用于说明启动流程。</p></body></topic>\n",
        encoding="utf-8",
    )

    window = MainWindow()
    window.en_to_zh_radio.setChecked(True)
    window.handle_source_path_received(str(source_file))

    assert window.zh_to_en_radio.isChecked() is True
    window.close()
    window.deleteLater()


def test_handle_source_path_received_uses_document_specific_language_detection_for_dita(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "chinese-with-code.dita"
    source_file.write_text(
        (
            "<topic id='demo'>"
            "<title>启动说明</title>"
            "<body>"
            "<p>本文档用于说明启动流程。</p>"
            "<codeblock>This code block contains many English words and driver configuration details.</codeblock>"
            "<screen>CONFIG_DRIVER_BOOT=1</screen>"
            "</body>"
            "</topic>\n"
        ),
        encoding="utf-8",
    )

    window = MainWindow()
    window.en_to_zh_radio.setChecked(True)
    window.handle_source_path_received(str(source_file))

    assert window.zh_to_en_radio.isChecked() is True
    window.close()
    window.deleteLater()


def test_commit_source_path_text_auto_switches_direction_without_warning(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "english.md"
    source_file.write_text(
        "This document explains the camera driver architecture in English.\n",
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow()
    window.source_path_edit.setText(str(source_file))
    window._commit_source_path_text()

    assert captured == {}
    assert window.en_to_zh_radio.isChecked() is True
    window.close()
    window.deleteLater()


def test_commit_source_path_text_accepts_dita_file(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "topic.dita"
    source_file.write_text(
        "<topic id='demo'><title>标题</title><body><p>本文档用于说明启动流程。</p></body></topic>\n",
        encoding="utf-8",
    )

    window = MainWindow()
    window.source_path_edit.setText(str(source_file))
    window._commit_source_path_text()

    assert window.source_path_edit.text() == str(source_file)
    assert window.output_dir_edit.text() == str(tmp_path)
    assert window.zh_to_en_radio.isChecked() is True
    window.close()
    window.deleteLater()


def test_handle_source_path_received_skips_language_detection_for_non_utf8_file(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "legacy.md"
    source_file.write_bytes(b"\xff\xfe\x00\x00")

    window = MainWindow()
    window.handle_source_path_received(str(source_file))

    log_text = window.log_output.toPlainText()
    assert window.source_path_edit.text() == str(source_file)
    assert "[语言] 自动检测失败，已跳过：" in log_text
    window.close()
    window.deleteLater()


def test_commit_output_directory_text_updates_output_dir(tmp_path: Path, qapp) -> None:
    window = MainWindow()
    window.output_dir_edit.setText(str(tmp_path))
    window._commit_output_directory_text()

    assert window.output_dir_edit.text() == str(tmp_path)
    window.close()
    window.deleteLater()


def test_validate_inputs_auto_fills_output_dir(tmp_path: Path, qapp) -> None:
    source_file = tmp_path / "validate-demo.md"
    source_file.write_text("# validate\n", encoding="utf-8")

    window = MainWindow()
    window.source_path_edit.setText(str(source_file))
    window.output_dir_edit.setText("")

    result = window.validate_inputs()

    assert result.valid is True
    assert window.output_dir_edit.text() == str(tmp_path)
    window.close()
    window.deleteLater()


def test_handle_start_clicked_shows_warning_for_invalid_inputs(
    monkeypatch: MonkeyPatch,
    qapp,
) -> None:
    captured: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow()
    window.source_path_edit.setText("")
    window.output_dir_edit.setText("")

    window.handle_start_clicked()

    assert captured["title"] == "输入校验失败"
    assert "目标翻译文件不能为空" in captured["message"]
    assert window.progress_label.text() == "输入校验失败"
    window.close()
    window.deleteLater()


def test_direction_toggle_warns_when_language_mismatches(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "english.md"
    source_file.write_text(
        "This document explains the camera driver architecture in English.\n",
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow()
    window.set_source_path(str(source_file))
    window.en_to_zh_radio.setChecked(True)
    window.zh_to_en_radio.setChecked(True)

    assert captured["title"] == "语言提示"
    assert "不是中文" in captured["message"]
    window.close()
    window.deleteLater()


def test_handle_start_clicked_starts_translation_task_after_language_warning(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "english.md"
    source_file.write_text(
        "This document explains the camera driver architecture in English.\n",
        encoding="utf-8",
    )
    captured: dict[str, object] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["warning_title"] = title
        captured["warning_message"] = message

    def fake_start(*, source_path: str, output_dir: str, direction: str) -> None:
        captured["source_path"] = source_path
        captured["output_dir"] = output_dir
        captured["direction"] = direction

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow()
    monkeypatch.setattr(window, "_start_translation_task", fake_start)
    window.source_path_edit.setText(str(source_file))
    window.output_dir_edit.setText(str(tmp_path))

    window.handle_start_clicked()

    assert captured["warning_title"] == "语言提示"
    assert "不是中文" in captured["warning_message"]
    assert captured["source_path"] == str(source_file)
    assert captured["output_dir"] == str(tmp_path)
    assert captured["direction"] == "zh_to_en"
    window.close()
    window.deleteLater()


def test_handle_translation_succeeded_updates_ui_and_shows_output(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    captured: dict[str, str] = {}

    def fake_information(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.information",
        fake_information,
    )

    window = MainWindow()
    result = TranslationPipelineResult(
        output_path=str(tmp_path / "demo_en.md"),
        final_markdown_text="demo",
        connection_message="OK",
        total_segments=3,
        total_batches=2,
        retry_attempts=1,
        overall_elapsed_seconds=130.0,
    )

    window._handle_translation_succeeded(result)
    log_text = window.log_output.toPlainText()

    assert window.progress_label.text() == "翻译完成（总耗时 02:10）"
    assert window.progress_bar.value() == 100
    assert captured["title"] == "翻译完成"
    assert str(tmp_path / "demo_en.md") in captured["message"]
    assert "[翻译] 平均每批耗时：01:05" in log_text
    assert "[翻译] 重试次数：1" in log_text
    window.close()
    window.deleteLater()


def test_append_log_adds_timestamp_and_elapsed_prefix_when_task_running(qapp) -> None:
    window = MainWindow()
    window._task_started_at = 0.0

    from doc_translation_tool.ui import main_window as main_window_module

    original_perf_counter = main_window_module.perf_counter
    main_window_module.perf_counter = lambda: 5.2
    try:
        window._append_log("[测试] 带耗时日志")
    finally:
        main_window_module.perf_counter = original_perf_counter

    log_text = window.log_output.toPlainText().splitlines()[-1]
    assert "[测试] 带耗时日志" in log_text
    assert re.search(r"^\[\d{2}:\d{2}:\d{2}\] \[\+5\.2s\] ", log_text) is not None
    window.close()
    window.deleteLater()


def test_handle_progress_updated_shows_elapsed_during_running_task(qapp) -> None:
    window = MainWindow()
    window._task_started_at = 0.0

    from doc_translation_tool.ui import main_window as main_window_module

    original_perf_counter = main_window_module.perf_counter
    main_window_module.perf_counter = lambda: 65.0
    try:
        window._handle_progress_updated("正在翻译批次 1/3", 50)
    finally:
        main_window_module.perf_counter = original_perf_counter

    assert "正在翻译批次 1/3" in window.progress_label.text()
    assert "已耗时 01:05" in window.progress_label.text()
    window.close()
    window.deleteLater()


def test_handle_worker_finished_prepares_next_translation_run(qapp) -> None:
    window = MainWindow()
    window.start_button.setEnabled(False)
    window.reset_button.setEnabled(False)

    window._handle_worker_finished()

    assert window.start_button.isEnabled() is True
    assert window.reset_button.isEnabled() is True
    assert window.start_button.text() == "开始下一次翻译"
    assert window.statusBar().currentMessage() == "当前任务已结束，可继续下一次翻译"
    window.close()
    window.deleteLater()


def test_handle_worker_finished_keeps_completion_status_context(qapp) -> None:
    window = MainWindow()
    window.statusBar().showMessage("翻译完成（总耗时 02:10）")

    window._handle_worker_finished()

    assert window.statusBar().currentMessage() == "翻译完成（总耗时 02:10），可继续下一次翻译"
    window.close()
    window.deleteLater()


def test_handle_reset_clicked_restores_idle_state_and_preserves_inputs(
    tmp_path: Path,
    qapp,
) -> None:
    source_file = tmp_path / "demo.md"
    source_file.write_text("# demo\n", encoding="utf-8")

    window = MainWindow(project_root=tmp_path)
    window.source_path_edit.setText(str(source_file))
    window.output_dir_edit.setText(str(tmp_path))
    window.en_to_zh_radio.setChecked(True)
    window.progress_bar.setValue(100)
    window.progress_label.setText("翻译完成")
    window.connection_hint_label.setText("模型状态：接口连通 (OK)")
    window.start_button.setText("开始下一次翻译")
    window.log_output.appendPlainText("[测试] 临时日志")

    window.handle_reset_clicked()

    log_text = window.log_output.toPlainText()
    assert window.source_path_edit.text() == str(source_file)
    assert window.output_dir_edit.text() == str(tmp_path)
    assert window.en_to_zh_radio.isChecked() is True
    assert window.progress_bar.value() == 0
    assert window.progress_label.text() == "等待开始翻译"
    assert window.connection_hint_label.text() == "模型状态：配置不完整"
    assert window.start_button.text() == "开始翻译"
    assert window.statusBar().currentMessage() == "界面已重置"
    assert "[系统] 界面已重置，可开始新的翻译任务。" in log_text
    assert "[测试] 临时日志" not in log_text
    window.close()
    window.deleteLater()


def test_handle_translation_failed_updates_ui_and_shows_error(
    monkeypatch: MonkeyPatch,
    qapp,
) -> None:
    captured: dict[str, str] = {}

    def fake_critical(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.critical",
        fake_critical,
    )

    window = MainWindow()
    window._handle_translation_failed("check_connection", "模型连接失败：network error")

    assert window.progress_label.text() == "模型连接失败"
    assert captured["title"] == "模型连接失败"
    assert "network error" in captured["message"]
    assert window.connection_hint_label.text() == "模型状态：接口检查失败"
    window.close()
    window.deleteLater()


def test_handle_translation_failed_shows_glossary_stage_suggestion(
    monkeypatch: MonkeyPatch,
    qapp,
) -> None:
    captured: dict[str, str] = {}

    def fake_critical(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.critical",
        fake_critical,
    )

    window = MainWindow()
    window._handle_translation_failed("glossary", "术语表加载失败：bad glossary")

    log_text = window.log_output.toPlainText()
    assert window.progress_label.text() == "术语表加载失败"
    assert captured["title"] == "术语表加载失败"
    assert "建议：" in captured["message"]
    assert "glossary.json" in captured["message"]
    assert "[建议]" in log_text
    window.close()
    window.deleteLater()


def test_handle_open_model_config_clicked_refreshes_model_status_after_save(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    class FakeDialog:
        class DialogCode:
            Accepted = QDialog.DialogCode.Accepted

        def __init__(self, *, project_root: Path, parent=None) -> None:
            del parent
            self.project_root = Path(project_root)

        def exec(self):
            (self.project_root / ".env").write_text(
                "\n".join(
                    [
                        "DOC_TRANS_BASE_URL=https://saved.example/v1",
                        "DOC_TRANS_API_KEY=saved-secret",
                        "DOC_TRANS_MODEL=saved-model",
                    ]
                )
                + "\n",
                encoding="utf-8",
            )
            return self.DialogCode.Accepted

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.ModelConfigDialog",
        FakeDialog,
    )

    window = MainWindow(project_root=tmp_path)

    assert window.connection_hint_label.text() == "模型状态：配置不完整"
    window.handle_open_model_config_clicked()

    assert window.connection_hint_label.text() == "模型状态：配置已加载，待检查连通性"
    assert window.statusBar().currentMessage() == "模型配置已保存"
    assert "模型配置已保存到 .env" in window.log_output.toPlainText()
    window.close()
    window.deleteLater()


def test_handle_open_glossary_config_clicked_saves_glossary_and_updates_status(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    class FakeDialog:
        class DialogCode:
            Accepted = QDialog.DialogCode.Accepted

        def __init__(self, *, project_root: Path, parent=None) -> None:
            del parent
            self.project_root = Path(project_root)

        def exec(self):
            (self.project_root / "glossary.json").write_text(
                '[{"source": "远程音效", "target": "remote sound effect"}]\n',
                encoding="utf-8",
            )
            return self.DialogCode.Accepted

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.GlossaryConfigDialog",
        FakeDialog,
    )

    window = MainWindow(project_root=tmp_path)

    window.handle_open_glossary_config_clicked()

    assert window.statusBar().currentMessage() == "术语配置已保存"
    assert "术语配置已保存到 glossary.json" in window.log_output.toPlainText()
    window.close()
    window.deleteLater()


def test_handle_open_glossary_config_clicked_shows_warning_on_load_failure(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    captured: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    class BrokenDialog:
        def __init__(self, *, project_root: Path, parent=None) -> None:
            del project_root, parent
            raise ValueError("bad glossary")

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.GlossaryConfigDialog",
        BrokenDialog,
    )
    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow(project_root=tmp_path)

    window.handle_open_glossary_config_clicked()

    assert captured["title"] == "术语配置加载失败"
    assert captured["message"] == "bad glossary"
    window.close()
    window.deleteLater()
