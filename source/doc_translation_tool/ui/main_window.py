from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QThread, QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from doc_translation_tool import __version__
from doc_translation_tool.config import load_app_settings
from doc_translation_tool.document_types import is_supported_document
from doc_translation_tool.models import BatchTranslationTask, TranslationTask
from doc_translation_tool.services import (
    BatchTranslationError,
    BatchTranslationPlan,
    BatchTranslationService,
    DocumentTranslationPipeline,
    TranslationPipelineError,
    TranslationPipelineResult,
)
from doc_translation_tool.services.lang_detect import (
    detect_language_for_document,
    direction_display_name,
    language_matches_direction,
)
from doc_translation_tool.services.validator import (
    InputValidationResult,
    validate_batch_translation_inputs,
    validate_translation_inputs,
)
from doc_translation_tool.ui.glossary_config_dialog import GlossaryConfigDialog
from doc_translation_tool.ui.model_config_dialog import ModelConfigDialog
from doc_translation_tool.ui.panels import (
    ActionBar,
    BatchTranslationPanel,
    LogGroup,
    ProgressGroup,
    TranslationPanel,
)


class TaskRunLogWriter:
    """Append task-scoped runtime logs to a per-run log file."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch(exist_ok=True)

    def append(self, message: str) -> None:
        with self.path.open("a", encoding="utf-8", newline="") as handle:
            handle.write(f"{message}\n")


class TranslationWorker(QThread):
    """Background worker that keeps the GUI responsive during translation."""

    progress_updated = Signal(str, int)
    log_message = Signal(str)
    connection_checked = Signal(str)
    segment_progress_updated = Signal(int, int, float)  # New: (completed, total, est_seconds)
    translation_succeeded = Signal(object)
    translation_failed = Signal(str, str)

    def __init__(
        self,
        pipeline: DocumentTranslationPipeline,
        task: TranslationTask,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.pipeline = pipeline
        self.task = task

    def run(self) -> None:
        try:
            result = self.pipeline.execute(
                self.task,
                on_log=self.log_message.emit,
                on_progress=self.progress_updated.emit,
                on_connection_checked=self.connection_checked.emit,
                on_segment_progress=self.segment_progress_updated.emit,
            )
        except TranslationPipelineError as exc:
            self.translation_failed.emit(exc.stage, exc.message)
            return
        except Exception as exc:  # pragma: no cover - defensive fallback
            self.translation_failed.emit("unknown", f"发生未预期错误：{exc}")
            return

        self.translation_succeeded.emit(result)


class BatchTranslationWorker(QThread):
    """Background worker for sequential directory batch translation."""

    progress_updated = Signal(str, int)
    log_message = Signal(str)
    batch_succeeded = Signal(object)
    batch_failed = Signal(str, str)

    def __init__(
        self,
        service: BatchTranslationService,
        task: BatchTranslationTask,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.service = service
        self.task = task

    def run(self) -> None:
        try:
            result = self.service.execute(
                self.task,
                on_log=self.log_message.emit,
                on_progress=self.progress_updated.emit,
            )
        except BatchTranslationError as exc:
            self.batch_failed.emit(exc.stage, exc.message)
            return
        except Exception as exc:  # pragma: no cover - defensive fallback
            self.batch_failed.emit("unknown", f"发生未预期错误：{exc}")
            return

        self.batch_succeeded.emit(result)


class LiveLogViewerDialog(QDialog):
    """Read-only dialog that keeps polling the current task log file."""

    _REFRESH_INTERVAL_MS = 600

    def __init__(
        self,
        *,
        log_path: Path,
        initial_text: str,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._log_path = Path(log_path)
        self._last_signature: tuple[int, int] | None = None

        self.setWindowTitle(f"详细日志 - {self._log_path.name}")
        self.resize(760, 520)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        path_label = QLabel(f"日志文件：{self._log_path}", self)
        path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_label.setWordWrap(True)

        self._log_view = QPlainTextEdit(self)
        self._log_view.setReadOnly(True)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        button_box.rejected.connect(self.reject)
        button_box.accepted.connect(self.accept)

        layout.addWidget(path_label)
        layout.addWidget(self._log_view, 1)
        layout.addWidget(button_box)

        self._timer = QTimer(self)
        self._timer.setInterval(self._REFRESH_INTERVAL_MS)
        self._timer.timeout.connect(self.refresh_log_contents)

        self._apply_log_text(initial_text)
        self.refresh_log_contents()
        self._timer.start()

    def _current_signature(self) -> tuple[int, int] | None:
        try:
            stat_result = self._log_path.stat()
        except OSError:
            return None
        return (stat_result.st_mtime_ns, stat_result.st_size)

    def _apply_log_text(self, log_text: str) -> None:
        current_text = self._log_view.toPlainText()
        if current_text == log_text:
            return

        scrollbar = self._log_view.verticalScrollBar()
        was_near_bottom = scrollbar.value() >= max(scrollbar.maximum() - 4, 0)
        current_value = scrollbar.value()

        self._log_view.setPlainText(log_text)

        if was_near_bottom:
            scrollbar.setValue(scrollbar.maximum())
        else:
            scrollbar.setValue(min(current_value, scrollbar.maximum()))

    def refresh_log_contents(self) -> None:
        signature = self._current_signature()
        if signature is None or signature == self._last_signature:
            return

        try:
            log_text = self._log_path.read_text(encoding="utf-8")
        except OSError:
            return

        self._last_signature = signature
        self._apply_log_text(log_text)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._timer.stop()
        super().closeEvent(event)


class MainWindow(QMainWindow):
    """Main application window for the desktop tool."""

    def __init__(self, *, project_root: str | Path | None = None) -> None:
        super().__init__()
        self.project_root = (
            Path(project_root)
            if project_root is not None
            else Path(__file__).resolve().parents[2]
        )
        self._worker: TranslationWorker | None = None
        self._task_started_at: float | None = None
        self._current_task: TranslationTask | None = None
        self._current_batch_task: BatchTranslationTask | None = None
        self._pending_batch_plan: BatchTranslationPlan | None = None
        self._task_log_writer: TaskRunLogWriter | None = None
        self._current_log_path: Path | None = None
        self._log_viewer_dialog: LiveLogViewerDialog | None = None
        self._segment_progress_text: str = ""

        # Create panel components
        self.translation_panel = TranslationPanel(self)
        self.batch_panel = BatchTranslationPanel(self)
        self.progress_group = ProgressGroup(self)
        self.log_group = LogGroup(self)
        self.action_bar = ActionBar(self)

        self.setWindowTitle(f"文档翻译工具 v{__version__}")
        self.resize(960, 680)
        self._build_ui()
        self._refresh_source_mode_ui()
        self._connect_signals()
        self._refresh_model_config_hint()

    # Property accessors for backward compatibility with tests
    @property
    def connection_hint_label(self):
        return self.action_bar.connection_hint_label

    @property
    def start_button(self):
        return self.action_bar.start_button

    @property
    def reset_button(self):
        return self.action_bar.reset_button

    @property
    def open_task_log_button(self):
        return self.action_bar.open_task_log_button

    @property
    def open_model_config_button(self):
        return self.action_bar.open_model_config_button

    @property
    def open_glossary_config_button(self):
        return self.action_bar.open_glossary_config_button

    @property
    def log_output(self):
        return self.log_group.log_output

    @property
    def progress_label(self):
        return self.progress_group.progress_label

    @property
    def progress_bar(self):
        return self.progress_group.progress_bar

    @property
    def source_path_edit(self):
        # In batch mode, return the directory edit; in single file mode, return the file edit
        if self.current_source_mode() == "directory":
            return self.batch_panel.source_dir_edit
        return self.translation_panel.source_path_edit

    @property
    def output_dir_edit(self):
        # Both panels have output_dir_edit, return based on current mode
        if self.current_source_mode() == "directory":
            return self.batch_panel.output_dir_edit
        return self.translation_panel.output_dir_edit

    @property
    def browse_source_button(self):
        if self.current_source_mode() == "directory":
            return self.batch_panel.browse_source_button
        return self.translation_panel.browse_source_button

    @property
    def zh_to_en_radio(self):
        if self.current_source_mode() == "directory":
            return self.batch_panel.zh_to_en_radio
        return self.translation_panel.zh_to_en_radio

    @property
    def en_to_zh_radio(self):
        if self.current_source_mode() == "directory":
            return self.batch_panel.en_to_zh_radio
        return self.translation_panel.en_to_zh_radio

    @property
    def direction_group(self):
        if self.current_source_mode() == "directory":
            return self.batch_panel.direction_group
        return self.translation_panel.direction_group

    @property
    def direction_hint_label(self):
        if self.current_source_mode() == "directory":
            return self.batch_panel.direction_hint_label
        return self.translation_panel.direction_hint_label

    @property
    def source_path_label(self):
        return self.batch_panel.source_path_label

    @property
    def clear_source_button(self):
        return self.batch_panel.clear_source_button

    def _build_ui(self) -> None:
        container = QWidget(self)
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        root_layout.addWidget(self._create_header())
        root_layout.addWidget(self._create_mode_group())

        # Add translation panels (only one visible at a time)
        root_layout.addWidget(self.translation_panel)
        root_layout.addWidget(self.batch_panel)

        root_layout.addWidget(self.progress_group)
        root_layout.addWidget(self.log_group, 1)
        root_layout.addWidget(self.action_bar)

        self.setCentralWidget(container)
        self.statusBar().showMessage("就绪")

    def _connect_signals(self) -> None:
        # Mode switching
        self.single_file_mode_radio.toggled.connect(self._handle_task_mode_toggled)
        self.batch_mode_radio.toggled.connect(self._handle_task_mode_toggled)

        # Translation panel signals
        self.translation_panel.source_path_changed.connect(self._handle_source_path_changed)
        self.translation_panel.output_directory_changed.connect(self._handle_output_directory_changed)
        self.translation_panel.direction_changed.connect(self._handle_direction_changed)

        # Batch panel signals
        self.batch_panel.source_directory_changed.connect(self._handle_source_directory_changed)
        self.batch_panel.output_directory_changed.connect(self._handle_output_directory_changed)
        self.batch_panel.default_direction_changed.connect(self._handle_direction_changed)

        # Action bar signals
        self.action_bar.start_button.clicked.connect(self.handle_start_clicked)
        self.action_bar.reset_button.clicked.connect(self.handle_reset_clicked)
        self.action_bar.open_model_config_button.clicked.connect(self.handle_open_model_config_clicked)
        self.action_bar.open_glossary_config_button.clicked.connect(self.handle_open_glossary_config_clicked)
        self.action_bar.open_task_log_button.clicked.connect(self.handle_open_task_log_clicked)

    def _create_header(self) -> QWidget:
        frame = QFrame(self)
        frame.setObjectName("headerFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        title_label = QLabel(f"文档翻译工具 v{__version__}", frame)
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("font-size: 24px; font-weight: 700;")

        subtitle_label = QLabel(
            "当前阶段：已接入单文件与目录批量、语言提醒、Markdown/DITA 文档处理、"
            "翻译结果回填以及输出文件写入。",
            frame,
        )
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("color: #555555;")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return frame

    def _create_mode_group(self) -> QGroupBox:
        group = QGroupBox("任务模式", self)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(24)

        self.single_file_mode_radio = QRadioButton("单文件", group)
        self.batch_mode_radio = QRadioButton("目录批量", group)
        self.single_file_mode_radio.setChecked(True)

        self.task_mode_button_group = QButtonGroup(group)
        self.task_mode_button_group.addButton(self.single_file_mode_radio)
        self.task_mode_button_group.addButton(self.batch_mode_radio)

        layout.addWidget(self.single_file_mode_radio)
        layout.addWidget(self.batch_mode_radio)
        layout.addStretch(1)
        return group

    def _refresh_model_config_hint(self) -> None:
        try:
            settings = load_app_settings(self.project_root)
        except Exception as exc:
            self._set_connection_hint(
                "模型状态：配置加载失败",
                f"读取配置失败：{exc}",
            )
            return

        missing_fields: list[str] = []
        if not settings.llm.base_url.strip():
            missing_fields.append("base_url")
        if not settings.llm.api_key.strip():
            missing_fields.append("api_key")
        if not settings.llm.model.strip():
            missing_fields.append("model")

        if missing_fields:
            self._set_connection_hint(
                "模型状态：配置不完整",
                "缺少关键项："
                + ", ".join(missing_fields)
                + "。开始翻译前请先补齐。"
            )
            return

        self._set_connection_hint(
            "模型状态：配置已加载，待检查连通性",
            "已检测到 base_url、api_key、model。实际连通性会在开始翻译时检查。"
        )

    def current_direction(self) -> str:
        if self.current_source_mode() == "directory":
            return self.batch_panel.get_default_direction()
        return self.translation_panel.get_direction()

    def current_source_mode(self) -> str:
        return "directory" if self.batch_mode_radio.isChecked() else "file"

    def _handle_task_mode_toggled(self, checked: bool) -> None:
        if not checked:
            return
        self._refresh_source_mode_ui()

    def _refresh_source_mode_ui(self) -> None:
        if self.current_source_mode() == "directory":
            self.translation_panel.hide()
            self.batch_panel.show()
        else:
            self.batch_panel.hide()
            self.translation_panel.show()

    # New signal handlers for panels
    def _handle_source_path_changed(self, source_path: str) -> None:
        self._apply_source_path(source_path, warn_trigger="path_changed")

    def handle_source_path_received(self, source_path: str) -> None:
        """Public alias for backward compatibility with tests."""
        if self.current_source_mode() == "directory":
            self._apply_source_directory(source_path)
        else:
            self._apply_source_path(source_path, warn_trigger="path_received")

    def _handle_source_directory_changed(self, source_directory: str) -> None:
        self._apply_source_directory(source_directory)

    def _handle_output_directory_changed(self, output_directory: str) -> None:
        self._apply_output_directory(output_directory)

    def _handle_direction_changed(self, direction: str) -> None:
        self._warn_if_language_mismatch(trigger="toggle")

    def handle_start_clicked(self) -> None:
        validation_result = self.validate_inputs()
        if not validation_result.valid:
            message = "\n".join(validation_result.errors)
            self.progress_group.set_progress("输入校验失败", 0)
            self.statusBar().showMessage("输入校验失败")
            QMessageBox.warning(self, "输入校验失败", message)
            return

        if self.current_source_mode() == "directory":
            task = BatchTranslationTask(
                source_dir=validation_result.source_path,
                output_dir=validation_result.output_dir,
                direction=self.current_direction(),
            )
            if not self._confirm_batch_translation_start(task):
                self.statusBar().showMessage("已取消目录批量翻译")
                return
            self._start_batch_translation_task(
                source_dir=task.source_dir,
                output_dir=task.output_dir,
                direction=task.direction,
            )
            return

        self._warn_if_language_mismatch(trigger="start")
        self._start_translation_task(
            source_path=validation_result.source_path,
            output_dir=validation_result.output_dir,
            direction=self.current_direction(),
        )

    def handle_open_model_config_clicked(self) -> None:
        if self._is_worker_running():
            return

        dialog = ModelConfigDialog(project_root=self.project_root, parent=self)
        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self._refresh_model_config_hint()
        self.statusBar().showMessage("模型配置已保存")

    def handle_open_glossary_config_clicked(self) -> None:
        if self._is_worker_running():
            return

        try:
            dialog = GlossaryConfigDialog(project_root=self.project_root, parent=self)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "术语配置加载失败", str(exc))
            return

        if dialog.exec() != dialog.DialogCode.Accepted:
            return

        self.statusBar().showMessage("术语配置已保存")

    def validate_inputs(self) -> InputValidationResult:
        if self.current_source_mode() == "directory":
            validation_result = validate_batch_translation_inputs(
                self.source_path_edit.text(),
                self.output_dir_edit.text(),
            )
        else:
            validation_result = validate_translation_inputs(
                self.source_path_edit.text(),
                self.output_dir_edit.text(),
            )

        if validation_result.source_path:
            self.source_path_edit.setText(validation_result.source_path)

        if validation_result.output_dir:
            self.output_dir_edit.setText(validation_result.output_dir)

        return validation_result

    def set_source_path(self, source_path: str) -> None:
        normalized_path = str(Path(source_path).expanduser())
        self.source_path_edit.setText(normalized_path)

        source_dir = str(Path(normalized_path).parent)
        self.output_dir_edit.setText(source_dir)

    def set_source_directory(self, source_directory: str) -> None:
        normalized_path = str(Path(source_directory).expanduser())
        self.source_path_edit.setText(normalized_path)
        self.output_dir_edit.setText(normalized_path)

    def set_output_directory(self, output_directory: str) -> None:
        normalized_path = str(Path(output_directory).expanduser())
        self.output_dir_edit.setText(normalized_path)

    def _commit_source_path_text(self) -> None:
        if self.current_source_mode() == "directory":
            source_directory = self._resolve_existing_source_directory()
            if source_directory is not None:
                self._apply_source_directory(str(source_directory))
            return

        source_path = self._resolve_supported_source_path()
        if source_path is not None:
            self._apply_source_path(str(source_path), warn_trigger="source")
            return

    def _commit_output_directory_text(self) -> None:
        output_path = self._resolve_existing_output_directory()
        if output_path is not None:
            self.set_output_directory(str(output_path))
            return

    def _handle_direction_toggled(self, checked: bool) -> None:
        if not checked:
            return
        if self.current_source_mode() == "directory":
            return
        self._warn_if_language_mismatch(trigger="toggle")

    def _auto_select_direction_from_source(self) -> None:
        source_path = self._resolve_supported_source_path()
        if source_path is None:
            return

        detection_result = detect_language_for_document(source_path)
        if not detection_result.is_confident:
            return

        if detection_result.language == "zh":
            if not self.zh_to_en_radio.isChecked():
                self.zh_to_en_radio.setChecked(True)
            return

        if detection_result.language == "en":
            if not self.en_to_zh_radio.isChecked():
                self.en_to_zh_radio.setChecked(True)

    def _warn_if_language_mismatch(self, *, trigger: str) -> None:
        source_path = self._resolve_supported_source_path()
        if source_path is None:
            return

        detection_result = detect_language_for_document(source_path)

        direction = self.current_direction()
        if not detection_result.is_confident:
            return
        if language_matches_direction(detection_result.language, direction):
            return

        if detection_result.language == "zh":
            message = "当前文件检测结果不是英文，请确认文件"
        else:
            message = "当前文件检测结果不是中文，请确认文件"

        if trigger in {"toggle", "start", "source"}:
            QMessageBox.warning(self, "语言提示", message)

    def _suggest_source_file_directory(self) -> str:
        source_text = self.source_path_edit.text().strip()
        if source_text:
            source_path = Path(source_text).expanduser()
            if source_path.is_dir():
                return str(source_path)
            return str(source_path.parent)

        output_path = self._resolve_existing_output_directory()
        if output_path is not None:
            return str(output_path)

        return str(Path.home())

    def _suggest_output_directory(self) -> str:
        output_path = self._resolve_existing_output_directory()
        if output_path is not None:
            return str(output_path)

        source_text = self.source_path_edit.text().strip()
        if source_text:
            source_path = Path(source_text).expanduser()
            if source_path.is_file():
                return str(source_path.parent)
            if source_path.is_dir():
                return str(source_path)

        return str(Path.home())

    def _append_summary_line(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_group.append_line(f"[{timestamp}] {message}")

    def _clear_summary(self) -> None:
        self.log_group.clear()

    def _format_runtime_log_message(self, message: str) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")
        if self._task_started_at is None:
            return f"[{timestamp}] {message}"

        elapsed = perf_counter() - self._task_started_at
        return f"[{timestamp}] [+{self._format_elapsed(elapsed)}] {message}"

    def _write_runtime_log(self, message: str) -> None:
        if self._task_log_writer is None:
            return
        try:
            self._task_log_writer.append(message)
        except OSError:
            return

    def _handle_runtime_log_message(self, message: str) -> None:
        self._write_runtime_log(self._format_runtime_log_message(message))

    def _build_task_log_path(self, *, source_path: str, output_dir: str) -> Path:
        source = Path(source_path)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        log_dir = Path(output_dir) / "logs"
        candidate = log_dir / f"{source.stem}_{timestamp}.log"
        suffix = 1
        while candidate.exists():
            candidate = log_dir / f"{source.stem}_{timestamp}_{suffix}.log"
            suffix += 1
        return candidate

    def _initialize_task_log(self, task: TranslationTask) -> None:
        self._current_log_path = self._build_task_log_path(
            source_path=task.source_path,
            output_dir=task.output_dir,
        )
        try:
            self._task_log_writer = TaskRunLogWriter(self._current_log_path)
        except OSError:
            self._task_log_writer = None
            self._current_log_path = None
            self._refresh_log_button_state()
            return

        self._refresh_log_button_state()

        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[任务] 开始翻译文件：{task.source_path}"
            )
        )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[任务] 输出目录：{task.output_dir}"
            )
        )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[任务] 翻译方向：{task.direction}"
            )
        )

    def _initialize_batch_log(self, task: BatchTranslationTask) -> None:
        self._current_log_path = self._build_task_log_path(
            source_path=task.source_dir or "directory_batch_task",
            output_dir=task.output_dir,
        )
        try:
            self._task_log_writer = TaskRunLogWriter(self._current_log_path)
        except OSError:
            self._task_log_writer = None
            self._current_log_path = None
            self._refresh_log_button_state()
            return

        self._refresh_log_button_state()

        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[目录批量] 源目录：{task.source_dir}"
            )
        )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[目录批量] 输出目录：{task.output_dir}"
            )
        )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[目录批量] 翻译方向：{task.direction}"
            )
        )

    def _confirm_batch_translation_start(self, task: BatchTranslationTask) -> bool:
        service = self._create_batch_translation_service()
        try:
            plan = service.build_execution_plan(task)
        except BatchTranslationError as exc:
            self._pending_batch_plan = None
            self.progress_group.set_progress("目录批量准备失败", 0)
            self.statusBar().showMessage("目录批量准备失败")
            QMessageBox.warning(self, "目录批量准备失败", exc.message)
            return False

        fallback_direction = direction_display_name(plan.fallback_direction)
        message = "\n".join(
            [
                f"源目录：{plan.source_dir}",
                f"支持文件：{plan.total_files} 个",
                f"识别为中文：{plan.detected_zh_files} 个，将按中译英处理",
                f"识别为英文：{plan.detected_en_files} 个，将按英译中处理",
                f"未确定：{plan.fallback_files} 个，将按默认方向“{fallback_direction}”处理",
                f"跳过不支持文件：{len(plan.skipped_paths)} 个",
                f"自动跳过疑似已生成输出：{plan.skipped_generated_files} 个",
                "",
                "确认开始目录批量翻译？",
            ]
        )
        confirmed = (
            QMessageBox.question(
                self,
                "确认目录批量翻译",
                message,
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.Yes,
            )
            == QMessageBox.StandardButton.Yes
        )
        self._pending_batch_plan = plan if confirmed else None
        return confirmed

    def _append_batch_plan_summary(self, plan: BatchTranslationPlan) -> None:
        fallback_direction = direction_display_name(plan.fallback_direction)
        summary_line = (
            "自动识别结果："
            f"中文 {plan.detected_zh_files}，"
            f"英文 {plan.detected_en_files}，"
            f"未确定 {plan.fallback_files}"
        )
        self._append_summary_line(summary_line)
        self._write_runtime_log(self._format_runtime_log_message(f"[目录批量] {summary_line}"))
        fallback_line = f"未确定文件默认方向：{fallback_direction}"
        self._append_summary_line(fallback_line)
        self._write_runtime_log(self._format_runtime_log_message(f"[目录批量] {fallback_line}"))
        if plan.skipped_paths:
            skip_line = f"已跳过不支持文件：{len(plan.skipped_paths)}"
            self._append_summary_line(skip_line)
            self._write_runtime_log(
                self._format_runtime_log_message(f"[目录批量] {skip_line}")
            )
        if plan.skipped_generated_files:
            generated_line = f"已自动跳过疑似已生成输出：{plan.skipped_generated_files}"
            self._append_summary_line(generated_line)
            self._write_runtime_log(
                self._format_runtime_log_message(f"[目录批量] {generated_line}")
            )

    def _build_running_progress_text(self) -> str:
        if self._current_task is None:
            return "正在翻译"
        source_name = Path(self._current_task.source_path).name
        if self._task_started_at is None:
            return f"开始翻译文件：{source_name}"
        elapsed = perf_counter() - self._task_started_at
        base_text = f"开始翻译文件：{source_name}（已耗时 {self._format_elapsed(elapsed)}）"

        # Append segment progress if available
        if self._segment_progress_text:
            return f"{base_text} - {self._segment_progress_text}"
        return base_text

    def _build_output_summary_line(self, output_path: str) -> str:
        direction = self._current_task.direction if self._current_task else self.current_direction()
        label = "英文" if direction == "zh_to_en" else "中文"
        return f"生成{label}文件：{Path(output_path).name}"

    def _format_elapsed(self, seconds: float) -> str:
        if seconds < 60:
            return f"{seconds:.1f}s"

        total_seconds = int(seconds)
        hours, remainder = divmod(total_seconds, 3600)
        minutes, secs = divmod(remainder, 60)
        if hours > 0:
            return f"{hours:02d}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    def handle_reset_clicked(self) -> None:
        if self._is_worker_running():
            return

        self._task_started_at = None
        self._current_task = None
        self._segment_progress_text = ""
        self._current_batch_task = None
        self._pending_batch_plan = None
        self._task_log_writer = None
        self._current_log_path = None
        self.progress_group.reset()
        self.action_bar.start_button.setText("开始翻译")
        self._clear_summary()
        self._refresh_log_button_state()
        self._refresh_model_config_hint()
        self.statusBar().showMessage("界面已重置")

    def _refresh_log_button_state(self) -> None:
        enabled = self._current_log_path is not None
        self.action_bar.set_log_button_enabled(enabled)
        if enabled:
            self.action_bar.open_task_log_button.setToolTip(
                f"查看当前任务日志：{self._current_log_path}"
            )
            return
        self.action_bar.open_task_log_button.setToolTip("当前任务生成日志后，可在这里查看完整内容。")

    def _show_log_viewer_dialog(self, log_path: Path, log_text: str) -> None:
        dialog = QDialog(self)
        dialog.setWindowTitle(f"详细日志 - {log_path.name}")
        dialog.resize(760, 520)

        layout = QVBoxLayout(dialog)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        path_label = QLabel(f"日志文件：{log_path}", dialog)
        path_label.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse
        )
        path_label.setWordWrap(True)

        log_view = QPlainTextEdit(dialog)
        log_view.setReadOnly(True)
        log_view.setPlainText(log_text)

        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, dialog)
        button_box.rejected.connect(dialog.reject)
        button_box.accepted.connect(dialog.accept)

        layout.addWidget(path_label)
        layout.addWidget(log_view, 1)
        layout.addWidget(button_box)
        dialog.exec()

    def _show_live_log_viewer_dialog(self, log_path: Path, log_text: str) -> None:
        existing_dialog = self._log_viewer_dialog
        if existing_dialog is not None and existing_dialog.isVisible():
            existing_dialog.refresh_log_contents()
            existing_dialog.raise_()
            existing_dialog.activateWindow()
            return

        dialog = LiveLogViewerDialog(
            log_path=log_path,
            initial_text=log_text,
            parent=self,
        )
        self._log_viewer_dialog = dialog
        dialog.finished.connect(self._handle_log_viewer_closed)
        dialog.exec()

    def _handle_log_viewer_closed(self) -> None:
        self._log_viewer_dialog = None

    def handle_open_task_log_clicked(self) -> None:
        if self._current_log_path is None:
            return

        try:
            log_text = self._current_log_path.read_text(encoding="utf-8")
        except OSError as exc:
            QMessageBox.warning(
                self,
                "读取日志失败",
                f"无法读取当前任务日志：{exc}\n\n日志文件：{self._current_log_path}",
            )
            return

        self._show_live_log_viewer_dialog(self._current_log_path, log_text)

    def _start_translation_task(
        self,
        *,
        source_path: str,
        output_dir: str,
        direction: str,
    ) -> None:
        if self._is_worker_running():
            return

        task = TranslationTask(
            source_path=source_path,
            output_dir=output_dir,
            direction=direction,
        )
        self._current_task = task
        self._task_started_at = perf_counter()
        self._initialize_task_log(task)
        worker = self._build_translation_worker(task)
        worker.progress_updated.connect(self._handle_progress_updated)
        worker.log_message.connect(self._handle_runtime_log_message)
        worker.connection_checked.connect(self._handle_connection_checked)
        worker.segment_progress_updated.connect(self._handle_segment_progress_updated)
        worker.translation_succeeded.connect(self._handle_translation_succeeded)
        worker.translation_failed.connect(self._handle_translation_failed)
        worker.finished.connect(self._handle_worker_finished)

        self._worker = worker
        self._set_action_buttons_enabled(False)
        self.action_bar.start_button.setText("翻译进行中")
        self.progress_group.set_progress(f"开始翻译文件：{Path(source_path).name}", 0)
        self._clear_summary()
        self._append_summary_line(f"开始翻译文件：{Path(source_path).name}")
        self._set_connection_hint(
            "模型状态：正在检查接口连通性",
            "正在验证当前配置是否能正常调用模型接口。",
        )
        self.statusBar().showMessage("正在执行翻译任务")
        worker.start()

    def _build_translation_worker(self, task: TranslationTask) -> TranslationWorker:
        pipeline = DocumentTranslationPipeline(project_root=self.project_root)
        return TranslationWorker(pipeline, task, self)

    def _start_batch_translation_task(
        self,
        *,
        source_dir: str,
        output_dir: str,
        direction: str,
    ) -> None:
        if self._is_worker_running():
            return

        task = BatchTranslationTask(
            source_dir=source_dir,
            output_dir=output_dir,
            direction=direction,
        )
        self._current_task = None
        self._current_batch_task = task
        self._task_started_at = perf_counter()
        self._initialize_batch_log(task)
        worker = self._build_batch_translation_worker(task)
        worker.progress_updated.connect(self._handle_batch_progress_updated)
        worker.log_message.connect(self._handle_runtime_log_message)
        worker.batch_succeeded.connect(self._handle_batch_translation_succeeded)
        worker.batch_failed.connect(self._handle_batch_translation_failed)
        worker.finished.connect(self._handle_worker_finished)

        self._worker = worker
        self._set_action_buttons_enabled(False)
        self.action_bar.start_button.setText("翻译进行中")
        self.progress_group.set_progress("正在准备目录批量翻译", 0)
        self._clear_summary()
        self._append_summary_line(f"开始目录批量翻译：{Path(source_dir).name}")
        if self._pending_batch_plan is not None:
            self._append_batch_plan_summary(self._pending_batch_plan)
        self._set_connection_hint(
            "模型状态：将在目录批量任务开始时检查连通性",
            "目录中的支持文件会按文件名顺序逐个翻译。",
        )
        self.statusBar().showMessage("正在执行目录批量翻译任务")
        worker.start()

    def _build_batch_translation_worker(
        self,
        task: BatchTranslationTask,
    ) -> BatchTranslationWorker:
        service = self._create_batch_translation_service()
        return BatchTranslationWorker(service, task, self)

    def _create_batch_translation_service(self) -> BatchTranslationService:
        return BatchTranslationService(
            pipeline_factory=lambda: DocumentTranslationPipeline(
                project_root=self.project_root
            )
        )

    def _handle_segment_progress_updated(self, completed: int, total: int, est_seconds: float) -> None:
        """Handle segment-level progress updates with time estimation."""
        if est_seconds > 0:
            est_text = self._format_elapsed(est_seconds)
            self._segment_progress_text = f"已翻译 {completed}/{total} 段，预计剩余 {est_text}"
        else:
            self._segment_progress_text = f"已翻译 {completed}/{total} 段"

        # Update the progress label with combined info
        display_message = self._build_running_progress_text()
        self.progress_group.progress_label.setText(display_message)
        self.statusBar().showMessage(display_message)

    def _handle_progress_updated(self, message: str, percent: int) -> None:
        self._write_runtime_log(
            self._format_runtime_log_message(f"[进度] {percent}% {message}")
        )
        display_message = self._build_running_progress_text()
        self.progress_group.set_progress(display_message, percent)
        self.statusBar().showMessage(display_message)

    def _handle_batch_progress_updated(self, message: str, percent: int) -> None:
        self._write_runtime_log(
            self._format_runtime_log_message(f"[批量进度] {percent}% {message}")
        )
        self.progress_group.set_progress(message, percent)
        self.statusBar().showMessage(message)
        if percent == 0 and message.startswith("开始批量翻译："):
            self._clear_summary()
            self._append_summary_line(message)

    def _handle_connection_checked(self, message: str) -> None:
        self._write_runtime_log(
            self._format_runtime_log_message(f"[模型] 接口连通：{message}")
        )
        self._set_connection_hint(
            f"模型状态：接口连通 ({message})",
            "已完成配置读取和接口连通性检查，可以继续执行翻译。",
        )

    def _handle_translation_succeeded(self, result: TranslationPipelineResult) -> None:
        self.progress_group.set_progress("翻译完成", 100)
        elapsed_seconds = result.overall_elapsed_seconds
        self.statusBar().showMessage("翻译完成")
        self._append_summary_line(self._build_output_summary_line(result.output_path))
        self._append_summary_line("翻译完成")
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[翻译] 总片段数：{result.total_segments}"
            )
        )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[翻译] 总批次数：{result.total_batches}"
            )
        )
        if result.total_batches > 0:
            average_batch_seconds = elapsed_seconds / result.total_batches
            self._write_runtime_log(
                self._format_runtime_log_message(
                    f"[翻译] 平均每批耗时：{self._format_elapsed(average_batch_seconds)}"
                )
            )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[翻译] 重试次数：{result.retry_attempts}"
            )
        )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[输出] 已生成输出文件：{result.output_path}"
            )
        )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[完成] 翻译完成，总耗时：{self._format_elapsed(elapsed_seconds)}"
            )
        )
        QMessageBox.information(
            self,
            "翻译完成",
            self._build_success_message(result.output_path),
        )

    def _handle_batch_translation_succeeded(self, result) -> None:
        summary_message = (
            f"目录批量翻译完成：成功 {result.successful_files}，"
            f"失败 {result.failed_files}，"
            f"跳过 {result.skipped_files}"
        )
        self.progress_group.set_progress(summary_message, 100)
        self.statusBar().showMessage(summary_message)
        self._append_summary_line(summary_message)
        for item in result.successful_results:
            self._append_summary_line(
                f"生成{'英文' if self.current_direction() == 'zh_to_en' else '中文'}文件：{Path(item.output_path).name}"
            )
        self._write_runtime_log(
            self._format_runtime_log_message(
                f"[批量] 汇总：成功 {result.successful_files}，失败 {result.failed_files}，跳过 {result.skipped_files}"
            )
        )
        QMessageBox.information(
            self,
            "目录批量翻译完成",
            summary_message,
        )

    def _handle_translation_failed(self, stage: str, message: str) -> None:
        stage_label = self._display_stage_name(stage)
        suggestion = self._failure_suggestion(stage, message)
        self.progress_label.setText("翻译失败，请查看日志文件")
        self.statusBar().showMessage("翻译失败，请查看日志文件")
        self._append_summary_line("翻译失败，请查看日志文件")
        if self._task_started_at is not None:
            self._write_runtime_log(
                self._format_runtime_log_message(
                    f"[失败] 当前任务已耗时：{self._format_elapsed(perf_counter() - self._task_started_at)}"
                )
            )
        self._write_runtime_log(
            self._format_runtime_log_message(f"[失败] {stage_label}：{message}")
        )
        if suggestion:
            self._write_runtime_log(
                self._format_runtime_log_message(f"[建议] {suggestion}")
            )
        if stage == "model_config":
            self._set_connection_hint(
                "模型状态：配置异常",
                "请先修正 .env 或 settings.json 中的模型配置。",
            )
        elif stage == "check_connection":
            self._set_connection_hint(
                "模型状态：接口检查失败",
                "配置已读取，但接口未通过连通性检查。",
            )
        QMessageBox.critical(
            self,
            f"{stage_label}失败",
            self._build_failure_message(message, suggestion),
        )

    def _handle_batch_translation_failed(self, stage: str, message: str) -> None:
        self.progress_label.setText("目录批量翻译失败，请查看日志文件")
        self.statusBar().showMessage("目录批量翻译失败，请查看日志文件")
        self._append_summary_line("目录批量翻译失败，请查看日志文件")
        self._write_runtime_log(
            self._format_runtime_log_message(f"[目录批量失败] {stage}：{message}")
        )
        error_message = message
        if self._current_log_path is not None:
            error_message = f"{message}\n\n日志文件：{self._current_log_path}"
        QMessageBox.critical(
            self,
            "目录批量翻译失败",
            error_message,
        )

    def _handle_worker_finished(self) -> None:
        self._set_action_buttons_enabled(True)
        self.action_bar.start_button.setText("开始下一次翻译")
        current_status = self.statusBar().currentMessage()
        if current_status == "翻译完成":
            self.statusBar().showMessage("翻译完成，可继续下一次翻译")
        elif current_status == "翻译失败，请查看日志文件":
            self.statusBar().showMessage("翻译失败，请查看日志文件，可调整后重试")
        elif current_status.startswith("目录批量翻译完成："):
            self.statusBar().showMessage(f"{current_status}，可继续下一次翻译")
        elif current_status == "目录批量翻译失败，请查看日志文件":
            self.statusBar().showMessage("目录批量翻译失败，请查看日志文件，可调整后重试")
        else:
            self.statusBar().showMessage("当前任务已结束，可继续下一次翻译")
        self._task_started_at = None
        self._current_task = None
        self._segment_progress_text = ""
        self._current_batch_task = None
        self._pending_batch_plan = None
        self._task_log_writer = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _is_worker_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _set_connection_hint(self, text: str, tooltip: str = "") -> None:
        self.action_bar.connection_hint_label.setText(text)
        self.action_bar.connection_hint_label.setToolTip(tooltip)

    def _set_action_buttons_enabled(self, enabled: bool) -> None:
        self.action_bar.start_button.setEnabled(enabled)
        self.open_model_config_button.setEnabled(enabled)
        self.open_glossary_config_button.setEnabled(enabled)
        self.action_bar.reset_button.setEnabled(enabled)
        self.clear_source_button.setEnabled(enabled)

    def _apply_source_path(self, source_path: str, *, warn_trigger: str) -> None:
        self.set_source_path(source_path)
        self._auto_select_direction_from_source()
        self._warn_if_language_mismatch(trigger=warn_trigger)

    def _apply_source_directory(self, source_directory: str) -> None:
        self.set_source_directory(source_directory)

    def _apply_output_directory(self, output_directory: str) -> None:
        self.set_output_directory(output_directory)

    def _resolve_supported_source_path(self) -> Path | None:
        source_text = self.source_path_edit.text().strip()
        if not source_text:
            return None

        source_path = Path(source_text).expanduser()
        if source_path.is_file() and is_supported_document(source_path):
            return source_path
        return None

    def _resolve_existing_source_directory(self) -> Path | None:
        source_text = self.source_path_edit.text().strip()
        if not source_text:
            return None

        source_path = Path(source_text).expanduser()
        if source_path.is_dir():
            return source_path
        return None

    def _resolve_existing_output_directory(self) -> Path | None:
        output_text = self.output_dir_edit.text().strip()
        if not output_text:
            return None

        output_path = Path(output_text).expanduser()
        if output_path.is_dir():
            return output_path
        return None

    def _display_stage_name(self, stage: str) -> str:
        mapping = {
            "read_source": "文件读取",
            "parse_document": "文档解析",
            "model_config": "模型配置",
            "glossary": "术语表加载",
            "check_connection": "模型连接",
            "translate": "翻译执行",
            "write_output": "输出写入",
            "unknown": "未知错误",
        }
        return mapping.get(stage, stage)

    def _failure_suggestion(self, stage: str, message: str) -> str:
        upper_message = message.upper()
        if ("429" in upper_message and "TOO MANY REQUESTS" in upper_message) or "HTTP 429" in upper_message:
            return (
                "接口返回 429，说明当前更像是限流、并发过高或服务端额度策略限制，"
                "不是 base_url、API key 或代理配置格式错误。请稍后重试，或避开高峰后再试。"
            )

        mapping = {
            "read_source": "请检查源文件路径、文件占用状态和 UTF-8 编码。",
            "parse_document": "请检查源文档是否完整且为合法格式。如果是 DITA/XML，请特别检查标签和结构是否关闭完整。",
            "model_config": "请检查 .env 或 settings.json 中的 base_url、api_key、model 等配置。",
            "glossary": "请检查 glossary.json 是否为 UTF-8 JSON 数组，且每项都包含 source 和 target。",
            "check_connection": "请检查接口地址、API key、网络连通性，以及本机代理配置是否干扰请求。",
            "translate": "请查看日志中的批次号和片段 ID，定位是哪个批次重试或最终失败。",
            "write_output": "请检查输出目录权限和文件占用状态，确认目标文件当前可被覆盖写入。",
            "unknown": "请查看日志中的最后一个失败阶段和上下文信息。",
        }
        return mapping.get(stage, "")

    def _build_failure_message(self, message: str, suggestion: str) -> str:
        parts = [message]
        if suggestion:
            parts.append(f"建议：{suggestion}")
        if self._current_log_path is not None:
            parts.append(f"日志文件：{self._current_log_path}")
        return "\n\n".join(parts)

    def _build_success_message(self, output_path: str) -> str:
        return f"翻译已完成，输出文件：{output_path}"
