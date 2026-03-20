import re
from pathlib import Path

from pytest import MonkeyPatch

from doc_translation_tool import __version__
from doc_translation_tool.services import TranslationPipelineResult
from doc_translation_tool.ui.main_window import MainWindow


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


def test_handle_source_path_received_warns_when_language_mismatches(
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

    assert captured["title"] == "语言提示"
    assert "不是中文" in captured["message"]
    window.close()
    window.deleteLater()


def test_commit_source_path_text_warns_when_language_mismatches(
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

    assert captured["title"] == "语言提示"
    assert "不是中文" in captured["message"]
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

    from doc_translation_tool.ui import main_window as main_window_module

    original_perf_counter = main_window_module.perf_counter
    main_window_module.perf_counter = lambda: 130.0

    window = MainWindow()
    window._task_started_at = 0.0
    result = TranslationPipelineResult(
        output_path=str(tmp_path / "demo_en.md"),
        final_markdown_text="demo",
        connection_message="OK",
        total_segments=3,
        total_batches=2,
        retry_attempts=1,
    )

    try:
        window._handle_translation_succeeded(result)
    finally:
        main_window_module.perf_counter = original_perf_counter
    log_text = window.log_output.toPlainText()

    assert window.progress_label.text() == "翻译完成"
    assert window.progress_bar.value() == 100
    assert captured["title"] == "翻译完成"
    assert str(tmp_path / "demo_en.md") in captured["message"]
    assert "[完成] 总耗时：02:10" in log_text
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


def test_handle_reset_clicked_restores_idle_state(tmp_path: Path, qapp) -> None:
    source_file = tmp_path / "demo.md"
    source_file.write_text("# demo\n", encoding="utf-8")

    window = MainWindow()
    window.source_path_edit.setText(str(source_file))
    window.output_dir_edit.setText(str(tmp_path))
    window.en_to_zh_radio.setChecked(True)
    window.progress_bar.setValue(100)
    window.progress_label.setText("翻译完成")
    window.connection_hint_label.setText("模型连接状态：已通过 (OK)")
    window.start_button.setText("开始下一次翻译")
    window.log_output.appendPlainText("[测试] 临时日志")

    window.handle_reset_clicked()

    log_text = window.log_output.toPlainText()
    assert window.source_path_edit.text() == ""
    assert window.output_dir_edit.text() == ""
    assert window.zh_to_en_radio.isChecked() is True
    assert window.progress_bar.value() == 0
    assert window.progress_label.text() == "等待开始翻译"
    assert window.connection_hint_label.text() == "模型连接状态：未检查"
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
    assert window.connection_hint_label.text() == "模型连接状态：失败"
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
