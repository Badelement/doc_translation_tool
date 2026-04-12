import re
from pathlib import Path
from types import SimpleNamespace

from pytest import MonkeyPatch
from PySide6.QtWidgets import QDialog, QMessageBox, QPlainTextEdit

from doc_translation_tool import __version__
from doc_translation_tool.models import BatchTranslationTask, TranslationTask
from doc_translation_tool.services import TranslationPipelineResult
from doc_translation_tool.ui.main_window import LiveLogViewerDialog, MainWindow


def assert_timestamped_summary(log_text: str, expected_fragment: str) -> None:
    matching_line = next(
        (line for line in log_text.splitlines() if expected_fragment in line),
        "",
    )
    assert matching_line
    assert re.search(r"^\[\d{2}:\d{2}:\d{2}\] ", matching_line) is not None


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
            self.segment_progress_updated = FakeSignal()
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
    assert_timestamped_summary(window.log_output.toPlainText(), "开始翻译文件：demo.md")
    assert window._current_log_path is not None
    assert window._current_log_path.exists() is True
    assert window._current_log_path.parent.name == "logs"
    assert window.open_task_log_button.isEnabled() is True
    window.close()
    window.deleteLater()


def test_switching_to_directory_batch_mode_updates_source_input_ui(qapp) -> None:
    window = MainWindow()

    window.batch_mode_radio.setChecked(True)

    assert window.current_source_mode() == "directory"
    assert window.source_path_label.text() == "源目录"
    assert window.browse_source_button.text() == "浏览目录"
    assert window.direction_group.title() == "默认翻译方向"
    assert window.direction_hint_label.isHidden() is False
    assert "只有未确定文件会使用这里的默认方向" in window.direction_hint_label.text()
    assert window.clear_source_button.isHidden() is False
    window.close()
    window.deleteLater()


def test_switching_back_to_single_file_restores_direction_group_text(qapp) -> None:
    window = MainWindow()
    window.batch_mode_radio.setChecked(True)
    window.single_file_mode_radio.setChecked(True)

    assert window.current_source_mode() == "file"
    assert window.direction_group.title() == "翻译方向"
    assert window.direction_hint_label.isHidden() is True
    window.close()
    window.deleteLater()


def test_handle_source_path_received_in_directory_mode_sets_source_and_output_dir(
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    window = MainWindow()
    window.batch_mode_radio.setChecked(True)

    window.handle_source_path_received(str(source_dir))

    assert window.source_path_edit.text() == str(source_dir)
    assert window.output_dir_edit.text() == str(source_dir)
    window.close()
    window.deleteLater()


def test_start_batch_translation_task_initializes_batch_worker_and_log(
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    window = MainWindow(project_root=tmp_path)
    window.batch_mode_radio.setChecked(True)

    class FakeSignal:
        def connect(self, _callback) -> None:
            return None

    class FakeBatchWorker:
        def __init__(self) -> None:
            self.progress_updated = FakeSignal()
            self.log_message = FakeSignal()
            self.batch_succeeded = FakeSignal()
            self.batch_failed = FakeSignal()
            self.finished = FakeSignal()

        def start(self) -> None:
            return None

        def isRunning(self) -> bool:
            return False

    window._worker = None
    window._build_batch_translation_worker = lambda _task: FakeBatchWorker()

    window._start_batch_translation_task(
        source_dir=str(source_dir),
        output_dir=str(output_dir),
        direction="zh_to_en",
    )

    assert window._current_batch_task is not None
    assert window._current_batch_task == BatchTranslationTask(
        source_dir=str(source_dir),
        output_dir=str(output_dir),
        direction="zh_to_en",
    )
    assert window.connection_hint_label.text() == "模型状态：将在目录批量任务开始时检查连通性"
    assert window.progress_label.text() == "正在准备目录批量翻译"
    assert_timestamped_summary(window.log_output.toPlainText(), "开始目录批量翻译：docs")
    assert window._current_log_path is not None
    assert window._current_log_path.exists() is True
    assert window._current_log_path.parent.name == "logs"
    assert window.open_task_log_button.isEnabled() is True
    window.close()
    window.deleteLater()


def test_handle_start_clicked_confirms_directory_batch_summary_before_start(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "a_zh.md").write_text(
        "本文档用于说明相机驱动架构和启动流程。\n",
        encoding="utf-8",
    )
    (source_dir / "b_en.md").write_text(
        "This document explains the camera driver startup sequence and runtime behavior in detail.\n",
        encoding="utf-8",
    )
    (source_dir / "c_unknown.md").write_text("v1.2.3\n", encoding="utf-8")
    (source_dir / "skip.txt").write_text("skip\n", encoding="utf-8")
    captured: dict[str, str] = {}
    started: dict[str, str] = {}

    def fake_question(_parent, title: str, message: str, *_args, **_kwargs):
        captured["title"] = title
        captured["message"] = message
        return QMessageBox.StandardButton.Yes

    def fake_start_batch_translation_task(*, source_dir: str, output_dir: str, direction: str) -> None:
        started["source_dir"] = source_dir
        started["output_dir"] = output_dir
        started["direction"] = direction

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.question",
        fake_question,
    )

    window = MainWindow()
    window.batch_mode_radio.setChecked(True)
    window.source_path_edit.setText(str(source_dir))
    window.output_dir_edit.setText(str(output_dir))
    window._start_batch_translation_task = fake_start_batch_translation_task

    window.handle_start_clicked()

    assert captured["title"] == "确认目录批量翻译"
    assert "支持文件：3 个" in captured["message"]
    assert "识别为中文：1 个，将按中译英处理" in captured["message"]
    assert "识别为英文：1 个，将按英译中处理" in captured["message"]
    assert "未确定：1 个，将按默认方向“中译英”处理" in captured["message"]
    assert "跳过不支持文件：1 个" in captured["message"]
    assert "自动跳过疑似已生成输出：0 个" in captured["message"]
    assert started == {
        "source_dir": str(source_dir),
        "output_dir": str(output_dir),
        "direction": "zh_to_en",
    }
    window.close()
    window.deleteLater()


def test_handle_start_clicked_appends_batch_plan_summary_after_confirmation(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "a_zh.md").write_text(
        "本文档用于说明相机驱动架构和启动流程。\n",
        encoding="utf-8",
    )
    (source_dir / "b_en.md").write_text(
        "This document explains the camera driver startup sequence and runtime behavior in detail.\n",
        encoding="utf-8",
    )
    (source_dir / "a_zh_en.md").write_text(
        "This is a previously generated translation.\n",
        encoding="utf-8",
    )

    def fake_question(_parent, _title: str, _message: str, *_args, **_kwargs):
        return QMessageBox.StandardButton.Yes

    class FakeSignal:
        def connect(self, _callback) -> None:
            return None

    class FakeBatchWorker:
        def __init__(self) -> None:
            self.progress_updated = FakeSignal()
            self.log_message = FakeSignal()
            self.batch_succeeded = FakeSignal()
            self.batch_failed = FakeSignal()
            self.finished = FakeSignal()

        def start(self) -> None:
            return None

        def isRunning(self) -> bool:
            return False

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.question",
        fake_question,
    )

    window = MainWindow(project_root=tmp_path)
    window.batch_mode_radio.setChecked(True)
    window.source_path_edit.setText(str(source_dir))
    window.output_dir_edit.setText(str(output_dir))
    window._worker = None
    window._build_batch_translation_worker = lambda _task: FakeBatchWorker()

    window.handle_start_clicked()

    log_text = window.log_output.toPlainText()
    assert "开始目录批量翻译：docs" in log_text
    assert "自动识别结果：中文 1，英文 1，未确定 0" in log_text
    assert "未确定文件默认方向：中译英" in log_text
    assert "已自动跳过疑似已生成输出：1" in log_text
    window.close()
    window.deleteLater()


def test_handle_start_clicked_cancels_directory_batch_when_user_declines(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "a.md").write_text(
        "本文档用于说明相机驱动架构和启动流程。\n",
        encoding="utf-8",
    )
    started: dict[str, str] = {}

    def fake_question(_parent, _title: str, _message: str, *_args, **_kwargs):
        return QMessageBox.StandardButton.No

    def fake_start_batch_translation_task(*, source_dir: str, output_dir: str, direction: str) -> None:
        started["source_dir"] = source_dir
        started["output_dir"] = output_dir
        started["direction"] = direction

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.question",
        fake_question,
    )

    window = MainWindow()
    window.batch_mode_radio.setChecked(True)
    window.source_path_edit.setText(str(source_dir))
    window.output_dir_edit.setText(str(output_dir))
    window._start_batch_translation_task = fake_start_batch_translation_task

    window.handle_start_clicked()

    assert started == {}
    assert window.statusBar().currentMessage() == "已取消目录批量翻译"
    window.close()
    window.deleteLater()


def test_handle_start_clicked_shows_warning_when_directory_has_no_supported_files(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "notes.txt").write_text("skip\n", encoding="utf-8")
    captured: dict[str, str] = {}
    started: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    def fake_start_batch_translation_task(*, source_dir: str, output_dir: str, direction: str) -> None:
        started["source_dir"] = source_dir
        started["output_dir"] = output_dir
        started["direction"] = direction

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow()
    window.batch_mode_radio.setChecked(True)
    window.source_path_edit.setText(str(source_dir))
    window.output_dir_edit.setText(str(output_dir))
    window._start_batch_translation_task = fake_start_batch_translation_task

    window.handle_start_clicked()

    assert captured["title"] == "目录批量准备失败"
    assert "未在源目录中找到支持的文档文件" in captured["message"]
    assert started == {}
    assert window.progress_label.text() == "目录批量准备失败"
    window.close()
    window.deleteLater()


def test_handle_start_clicked_summary_includes_generated_output_skip_count(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    output_dir = tmp_path / "out"
    output_dir.mkdir()
    (source_dir / "guide.md").write_text(
        "本文档用于说明相机驱动架构和启动流程。\n",
        encoding="utf-8",
    )
    (source_dir / "guide_en.md").write_text(
        "This is a previously generated translation.\n",
        encoding="utf-8",
    )
    captured: dict[str, str] = {}

    def fake_question(_parent, title: str, message: str, *_args, **_kwargs):
        captured["title"] = title
        captured["message"] = message
        return QMessageBox.StandardButton.No

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.question",
        fake_question,
    )

    window = MainWindow()
    window.batch_mode_radio.setChecked(True)
    window.source_path_edit.setText(str(source_dir))
    window.output_dir_edit.setText(str(output_dir))

    window.handle_start_clicked()

    assert captured["title"] == "确认目录批量翻译"
    assert "支持文件：1 个" in captured["message"]
    assert "自动跳过疑似已生成输出：1 个" in captured["message"]
    window.close()
    window.deleteLater()


def test_handle_connection_checked_updates_model_status_to_connected(qapp) -> None:
    window = MainWindow()

    window._handle_connection_checked("OK")

    assert window.connection_hint_label.text() == "模型状态：接口连通 (OK)"
    assert "接口连通性检查" in window.connection_hint_label.toolTip()
    window.close()
    window.deleteLater()


def test_handle_batch_translation_succeeded_updates_ui_and_summary(
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
    window.batch_mode_radio.setChecked(True)
    result = SimpleNamespace(
        successful_files=2,
        failed_files=1,
        skipped_files=1,
        successful_results=[
            SimpleNamespace(output_path=str(tmp_path / "a_en.md")),
            SimpleNamespace(output_path=str(tmp_path / "b_en.dita")),
        ],
    )

    window._handle_batch_translation_succeeded(result)

    assert window.progress_label.text() == "目录批量翻译完成：成功 2，失败 1，跳过 1"
    assert "生成英文文件：a_en.md" in window.log_output.toPlainText()
    assert captured["title"] == "目录批量翻译完成"
    assert "成功 2，失败 1，跳过 1" in captured["message"]
    window.close()
    window.deleteLater()


def test_suggest_output_directory_prefers_source_dir_in_directory_mode(
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()

    window = MainWindow()
    window.batch_mode_radio.setChecked(True)
    window.handle_source_path_received(str(source_dir))
    window.output_dir_edit.clear()

    assert window._suggest_output_directory() == str(source_dir)
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


def test_directory_mode_direction_toggle_does_not_warn_without_single_file(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    source_dir = tmp_path / "docs"
    source_dir.mkdir()
    captured: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow()
    window.batch_mode_radio.setChecked(True)
    window.handle_source_path_received(str(source_dir))
    window.en_to_zh_radio.setChecked(True)
    window.zh_to_en_radio.setChecked(True)

    assert captured == {}
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
    window._current_task = TranslationTask(
        source_path=str(tmp_path / "demo.md"),
        output_dir=str(tmp_path),
        direction="zh_to_en",
    )
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

    assert window.progress_label.text() == "翻译完成"
    assert window.progress_bar.value() == 100
    assert captured["title"] == "翻译完成"
    assert str(tmp_path / "demo_en.md") in captured["message"]
    assert "运行日志：" not in captured["message"]
    assert "生成英文文件：demo_en.md" in log_text
    assert "翻译完成" in log_text
    window.close()
    window.deleteLater()


def test_handle_runtime_log_message_writes_timestamped_line_to_task_log(
    tmp_path: Path,
    qapp,
) -> None:
    window = MainWindow()
    window._current_task = TranslationTask(
        source_path=str(tmp_path / "demo.md"),
        output_dir=str(tmp_path),
        direction="zh_to_en",
    )
    window._task_started_at = 0.0
    window._initialize_task_log(window._current_task)

    from doc_translation_tool.ui import main_window as main_window_module

    original_perf_counter = main_window_module.perf_counter
    main_window_module.perf_counter = lambda: 5.2
    try:
        window._handle_runtime_log_message("[测试] 带耗时日志")
    finally:
        main_window_module.perf_counter = original_perf_counter

    assert window._current_log_path is not None
    log_text = window._current_log_path.read_text(encoding="utf-8").splitlines()[-1]
    assert "[测试] 带耗时日志" in log_text
    assert re.search(r"^\[\d{2}:\d{2}:\d{2}\] \[\+5\.2s\] ", log_text) is not None
    window.close()
    window.deleteLater()


def test_log_button_is_disabled_before_task_log_is_initialized(qapp) -> None:
    window = MainWindow()

    assert window.open_task_log_button.isEnabled() is False

    window.close()
    window.deleteLater()


def test_handle_open_task_log_clicked_shows_current_log_contents(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    log_path = tmp_path / "logs" / "demo.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("[12:00:00] test log\n", encoding="utf-8")
    captured: dict[str, str] = {}

    def fake_show_log_viewer_dialog(log_file: Path, log_text: str) -> None:
        captured["path"] = str(log_file)
        captured["text"] = log_text

    window = MainWindow()
    window._current_log_path = log_path
    window._refresh_log_button_state()
    monkeypatch.setattr(window, "_show_live_log_viewer_dialog", fake_show_log_viewer_dialog)

    window.handle_open_task_log_clicked()

    assert captured["path"] == str(log_path)
    assert captured["text"] == "[12:00:00] test log\n"
    window.close()
    window.deleteLater()


def test_live_log_viewer_dialog_refreshes_when_log_file_grows(
    tmp_path: Path,
    qapp,
) -> None:
    log_path = tmp_path / "logs" / "demo.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("[12:00:00] first line\n", encoding="utf-8")

    dialog = LiveLogViewerDialog(
        log_path=log_path,
        initial_text="[12:00:00] first line\n",
    )

    log_path.write_text(
        "[12:00:00] first line\n[12:00:01] second line\n",
        encoding="utf-8",
    )
    dialog.refresh_log_contents()

    assert "[12:00:01] second line" in dialog.findChild(QPlainTextEdit).toPlainText()
    dialog.close()


def test_handle_open_task_log_clicked_warns_when_log_cannot_be_read(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    missing_log_path = tmp_path / "logs" / "missing.log"
    captured: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.main_window.QMessageBox.warning",
        fake_warning,
    )

    window = MainWindow()
    window._current_log_path = missing_log_path
    window._refresh_log_button_state()

    window.handle_open_task_log_clicked()

    assert captured["title"] == "读取日志失败"
    assert str(missing_log_path) in captured["message"]
    window.close()
    window.deleteLater()


def test_handle_progress_updated_shows_elapsed_during_running_task(
    tmp_path: Path,
    qapp,
) -> None:
    window = MainWindow()
    window._current_task = TranslationTask(
        source_path=str(tmp_path / "demo.md"),
        output_dir=str(tmp_path),
        direction="zh_to_en",
    )
    window._task_started_at = 0.0

    from doc_translation_tool.ui import main_window as main_window_module

    original_perf_counter = main_window_module.perf_counter
    main_window_module.perf_counter = lambda: 65.0
    try:
        window._handle_progress_updated("正在翻译批次 1/3", 50)
    finally:
        main_window_module.perf_counter = original_perf_counter

    assert "开始翻译文件：demo.md" in window.progress_label.text()
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
    window.statusBar().showMessage("翻译完成")

    window._handle_worker_finished()

    assert window.statusBar().currentMessage() == "翻译完成，可继续下一次翻译"
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
    window._current_task = TranslationTask(
        source_path=str(source_file),
        output_dir=str(tmp_path),
        direction="en_to_zh",
    )
    window._current_log_path = tmp_path / "logs" / "demo.log"
    window._refresh_log_button_state()
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
    assert log_text == ""
    assert window._current_log_path is None
    assert window.open_task_log_button.isEnabled() is False
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
    window._current_log_path = Path("C:/logs/demo.log")
    window._handle_translation_failed("check_connection", "模型连接失败：network error")

    assert window.progress_label.text() == "翻译失败，请查看日志文件"
    assert captured["title"] == "模型连接失败"
    assert "network error" in captured["message"]
    assert "日志文件：" in captured["message"]
    assert window.connection_hint_label.text() == "模型状态：接口检查失败"
    assert "翻译失败，请查看日志文件" in window.log_output.toPlainText()
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
    window._current_log_path = Path("C:/logs/demo.log")
    window._handle_translation_failed("glossary", "术语表加载失败：bad glossary")

    log_text = window.log_output.toPlainText()
    assert window.progress_label.text() == "翻译失败，请查看日志文件"
    assert captured["title"] == "术语表加载失败"
    assert "建议：" in captured["message"]
    assert "glossary.json" in captured["message"]
    assert "翻译失败，请查看日志文件" in log_text
    window.close()
    window.deleteLater()


def test_handle_translation_failed_shows_parse_document_stage_suggestion(
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
    window._handle_translation_failed("parse_document", "文档解析失败：no element found")

    assert window.progress_label.text() == "翻译失败，请查看日志文件"
    assert captured["title"] == "文档解析失败"
    assert "DITA/XML" in captured["message"]
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
