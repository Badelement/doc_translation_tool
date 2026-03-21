from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import perf_counter

from PySide6.QtCore import QThread, Qt, Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QRadioButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from doc_translation_tool import __version__
from doc_translation_tool.config import load_app_settings
from doc_translation_tool.models import TranslationTask
from doc_translation_tool.services import (
    DocumentTranslationPipeline,
    TranslationPipelineError,
    TranslationPipelineResult,
)
from doc_translation_tool.services.lang_detect import (
    detect_language_from_file,
    direction_display_name,
    language_matches_direction,
)
from doc_translation_tool.services.validator import validate_translation_inputs
from doc_translation_tool.ui.path_line_edit import PathLineEdit


class TranslationWorker(QThread):
    """Background worker that keeps the GUI responsive during translation."""

    progress_updated = Signal(str, int)
    log_message = Signal(str)
    connection_checked = Signal(str)
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
            )
        except TranslationPipelineError as exc:
            self.translation_failed.emit(exc.stage, exc.message)
            return
        except Exception as exc:  # pragma: no cover - defensive fallback
            self.translation_failed.emit("unknown", f"发生未预期错误：{exc}")
            return

        self.translation_succeeded.emit(result)


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
        self.setWindowTitle(f"文档翻译工具 v{__version__}")
        self.resize(960, 680)
        self._build_ui()
        self._connect_signals()
        self._refresh_model_config_hint()

    def _build_ui(self) -> None:
        container = QWidget(self)
        root_layout = QVBoxLayout(container)
        root_layout.setContentsMargins(20, 20, 20, 20)
        root_layout.setSpacing(16)

        root_layout.addWidget(self._create_header())
        root_layout.addWidget(self._create_path_group())
        root_layout.addWidget(self._create_direction_group())
        root_layout.addWidget(self._create_progress_group())
        root_layout.addWidget(self._create_log_group(), 1)
        root_layout.addLayout(self._create_action_row())

        self.setCentralWidget(container)
        self.statusBar().showMessage("就绪")

    def _connect_signals(self) -> None:
        self.browse_source_button.clicked.connect(self.select_source_file)
        self.browse_output_button.clicked.connect(self.select_output_directory)
        self.source_path_edit.editingFinished.connect(self._commit_source_path_text)
        self.output_dir_edit.editingFinished.connect(self._commit_output_directory_text)
        self.zh_to_en_radio.toggled.connect(self._handle_direction_toggled)
        self.en_to_zh_radio.toggled.connect(self._handle_direction_toggled)
        self.reset_button.clicked.connect(self.handle_reset_clicked)
        self.start_button.clicked.connect(self.handle_start_clicked)

    def _create_header(self) -> QWidget:
        frame = QFrame(self)
        frame.setObjectName("headerFrame")
        layout = QVBoxLayout(frame)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(6)

        title_label = QLabel(f"Markdown 文档翻译工具 v{__version__}", frame)
        title_label.setObjectName("titleLabel")
        title_label.setStyleSheet("font-size: 24px; font-weight: 700;")

        subtitle_label = QLabel(
            "当前阶段：已接入文件与目录选择、语言提醒、Markdown 保护分段、"
            "批量翻译回填以及输出文件写入。",
            frame,
        )
        subtitle_label.setWordWrap(True)
        subtitle_label.setStyleSheet("color: #555555;")

        layout.addWidget(title_label)
        layout.addWidget(subtitle_label)
        return frame

    def _create_path_group(self) -> QGroupBox:
        group = QGroupBox("路径设置", self)
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        source_label = QLabel("目标翻译文件", group)
        output_label = QLabel("生成目录", group)

        self.source_path_edit = PathLineEdit(
            path_kind="markdown_file",
            on_path_received=self.handle_source_path_received,
            parent=group,
        )
        self.source_path_edit.setPlaceholderText("请选择、拖入或粘贴 .md 文件路径")

        self.output_dir_edit = PathLineEdit(
            path_kind="directory",
            on_path_received=self.handle_output_directory_received,
            parent=group,
        )
        self.output_dir_edit.setPlaceholderText("请选择、拖入或粘贴输出目录路径")

        self.browse_source_button = QPushButton("浏览文件", group)
        self.browse_output_button = QPushButton("浏览目录", group)

        self.source_path_edit.setObjectName("sourcePathEdit")
        self.output_dir_edit.setObjectName("outputDirEdit")
        self.browse_source_button.setObjectName("browseSourceButton")
        self.browse_output_button.setObjectName("browseOutputButton")

        layout.addWidget(source_label, 0, 0)
        layout.addWidget(self.source_path_edit, 0, 1)
        layout.addWidget(self.browse_source_button, 0, 2)
        layout.addWidget(output_label, 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1)
        layout.addWidget(self.browse_output_button, 1, 2)
        layout.setColumnStretch(1, 1)
        return group

    def _create_direction_group(self) -> QGroupBox:
        group = QGroupBox("翻译方向", self)
        layout = QHBoxLayout(group)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(24)

        self.zh_to_en_radio = QRadioButton("中译英", group)
        self.en_to_zh_radio = QRadioButton("英译中", group)
        self.zh_to_en_radio.setChecked(True)

        self.direction_button_group = QButtonGroup(group)
        self.direction_button_group.addButton(self.zh_to_en_radio)
        self.direction_button_group.addButton(self.en_to_zh_radio)

        layout.addWidget(self.zh_to_en_radio)
        layout.addWidget(self.en_to_zh_radio)
        layout.addStretch(1)
        return group

    def _create_progress_group(self) -> QGroupBox:
        group = QGroupBox("任务状态", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 14, 16, 16)
        layout.setSpacing(10)

        self.progress_label = QLabel("等待开始翻译", group)
        self.progress_bar = QProgressBar(group)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")

        layout.addWidget(self.progress_label)
        layout.addWidget(self.progress_bar)
        return group

    def _create_log_group(self) -> QGroupBox:
        group = QGroupBox("日志输出", self)
        layout = QVBoxLayout(group)
        layout.setContentsMargins(16, 14, 16, 16)

        self.log_output = QPlainTextEdit(group)
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("logOutput")
        self.log_output.setPlaceholderText("运行日志会显示在这里。")
        self.log_output.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )
        self._seed_initial_logs()

        layout.addWidget(self.log_output)
        return group

    def _create_action_row(self) -> QHBoxLayout:
        layout = QHBoxLayout()
        layout.setSpacing(12)

        self.connection_hint_label = QLabel("模型状态：未检查", self)
        self.connection_hint_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        self.start_button = QPushButton("开始翻译", self)
        self.start_button.setObjectName("startButton")
        self.start_button.setMinimumHeight(40)

        self.reset_button = QPushButton("重置界面", self)
        self.reset_button.setObjectName("resetButton")
        self.reset_button.setMinimumHeight(40)

        layout.addWidget(self.connection_hint_label, 1)
        layout.addWidget(self.reset_button, 0)
        layout.addWidget(self.start_button, 0)
        return layout

    def _refresh_model_config_hint(self) -> None:
        try:
            settings = load_app_settings(self.project_root)
        except Exception as exc:
            self.connection_hint_label.setText("模型状态：配置加载失败")
            self.connection_hint_label.setToolTip(f"读取配置失败：{exc}")
            return

        missing_fields: list[str] = []
        if not settings.llm.base_url.strip():
            missing_fields.append("base_url")
        if not settings.llm.api_key.strip():
            missing_fields.append("api_key")
        if not settings.llm.model.strip():
            missing_fields.append("model")

        if missing_fields:
            self.connection_hint_label.setText("模型状态：配置不完整")
            self.connection_hint_label.setToolTip(
                "缺少关键项："
                + ", ".join(missing_fields)
                + "。开始翻译前请先补齐。"
            )
            return

        self.connection_hint_label.setText("模型状态：配置已加载，待检查连通性")
        self.connection_hint_label.setToolTip(
            "已检测到 base_url、api_key、model。实际连通性会在开始翻译时检查。"
        )

    def current_direction(self) -> str:
        return "zh_to_en" if self.zh_to_en_radio.isChecked() else "en_to_zh"

    def select_source_file(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择目标翻译文件",
            self._suggest_source_file_directory(),
            "Markdown Files (*.md);;All Files (*)",
        )
        if not selected_path:
            return

        self.handle_source_path_received(selected_path)
        self.statusBar().showMessage("已选择目标翻译文件")

    def select_output_directory(self) -> None:
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "选择生成目录",
            self._suggest_output_directory(),
        )
        if not selected_directory:
            return

        self.handle_output_directory_received(selected_directory)
        self.statusBar().showMessage("已选择生成目录")

    def handle_source_path_received(self, source_path: str) -> None:
        self.set_source_path(source_path)
        self._auto_select_direction_from_source()
        self._warn_if_language_mismatch(trigger="source")
        self.statusBar().showMessage("已更新目标翻译文件")

    def handle_output_directory_received(self, output_directory: str) -> None:
        self.set_output_directory(output_directory)
        self.statusBar().showMessage("已更新生成目录")

    def handle_start_clicked(self) -> None:
        validation_result = self.validate_inputs()
        if not validation_result.valid:
            message = "\n".join(validation_result.errors)
            self.progress_label.setText("输入校验失败")
            self.statusBar().showMessage("输入校验失败")
            self._append_log(f"[校验] 失败：{message}")
            QMessageBox.warning(self, "输入校验失败", message)
            return

        self._warn_if_language_mismatch(trigger="start")
        self._append_log("[校验] 输入校验通过。")
        self._start_translation_task(
            source_path=validation_result.source_path,
            output_dir=validation_result.output_dir,
            direction=self.current_direction(),
        )

    def validate_inputs(self):
        validation_result = validate_translation_inputs(
            self.source_path_edit.text(),
            self.output_dir_edit.text(),
        )

        if validation_result.source_path:
            self.source_path_edit.setText(validation_result.source_path)

        if validation_result.output_dir:
            self.output_dir_edit.setText(validation_result.output_dir)

        if validation_result.auto_filled_output_dir and validation_result.output_dir:
            self._append_log(
                f"[校验] 生成目录为空，已自动补全为：{validation_result.output_dir}"
            )

        return validation_result

    def set_source_path(self, source_path: str) -> None:
        normalized_path = str(Path(source_path).expanduser())
        self.source_path_edit.setText(normalized_path)

        source_dir = str(Path(normalized_path).parent)
        self.output_dir_edit.setText(source_dir)

        self._append_log(f"[路径] 目标翻译文件：{normalized_path}")
        self._append_log(f"[路径] 已同步生成目录：{source_dir}")

    def set_output_directory(self, output_directory: str) -> None:
        normalized_path = str(Path(output_directory).expanduser())
        self.output_dir_edit.setText(normalized_path)
        self._append_log(f"[路径] 生成目录：{normalized_path}")

    def _commit_source_path_text(self) -> None:
        source_text = self.source_path_edit.text().strip()
        if not source_text:
            return

        source_path = Path(source_text).expanduser()
        if source_path.is_file() and source_path.suffix.lower() == ".md":
            self.set_source_path(str(source_path))
            self._auto_select_direction_from_source()
            self._warn_if_language_mismatch(trigger="source")
            return

        self._append_log(f"[路径] 未识别为有效 Markdown 文件：{source_text}")

    def _commit_output_directory_text(self) -> None:
        output_text = self.output_dir_edit.text().strip()
        if not output_text:
            return

        output_path = Path(output_text).expanduser()
        if output_path.is_dir():
            self.set_output_directory(str(output_path))
            return

        self._append_log(f"[路径] 未识别为有效输出目录：{output_text}")

    def _handle_direction_toggled(self, checked: bool) -> None:
        if not checked:
            return
        self._warn_if_language_mismatch(trigger="toggle")

    def _auto_select_direction_from_source(self) -> None:
        source_text = self.source_path_edit.text().strip()
        if not source_text:
            return

        source_path = Path(source_text).expanduser()
        if not source_path.is_file() or source_path.suffix.lower() != ".md":
            return

        detection_result = detect_language_from_file(source_path)
        if not detection_result.is_confident:
            return

        if detection_result.language == "zh":
            if not self.zh_to_en_radio.isChecked():
                self.zh_to_en_radio.setChecked(True)
                self._append_log("[语言] 检测到中文内容，已自动切换为：中译英")
            return

        if detection_result.language == "en":
            if not self.en_to_zh_radio.isChecked():
                self.en_to_zh_radio.setChecked(True)
                self._append_log("[语言] 检测到英文内容，已自动切换为：英译中")

    def _warn_if_language_mismatch(self, *, trigger: str) -> None:
        source_text = self.source_path_edit.text().strip()
        if not source_text:
            return

        source_path = Path(source_text).expanduser()
        if not source_path.is_file() or source_path.suffix.lower() != ".md":
            return

        detection_result = detect_language_from_file(source_path)
        self._append_log(
            "[语言] 检测结果："
            f"{detection_result.language} "
            f"(zh={detection_result.zh_char_count}, en={detection_result.en_word_count})"
        )

        direction = self.current_direction()
        if not detection_result.is_confident:
            return
        if language_matches_direction(detection_result.language, direction):
            return

        if detection_result.language == "zh":
            message = "当前文件检测结果不是英文，请确认文件"
        else:
            message = "当前文件检测结果不是中文，请确认文件"

        self._append_log(
            f"[语言] 方向 {direction_display_name(direction)} 与文件语言不匹配：{message}"
        )

        if trigger in {"toggle", "start", "source"}:
            QMessageBox.warning(self, "语言提示", message)

    def _suggest_source_file_directory(self) -> str:
        source_text = self.source_path_edit.text().strip()
        if source_text:
            source_path = Path(source_text).expanduser()
            if source_path.is_dir():
                return str(source_path)
            return str(source_path.parent)

        output_text = self.output_dir_edit.text().strip()
        if output_text:
            output_path = Path(output_text).expanduser()
            if output_path.is_dir():
                return str(output_path)

        return str(Path.home())

    def _suggest_output_directory(self) -> str:
        output_text = self.output_dir_edit.text().strip()
        if output_text:
            output_path = Path(output_text).expanduser()
            if output_path.is_dir():
                return str(output_path)

        source_text = self.source_path_edit.text().strip()
        if source_text:
            source_path = Path(source_text).expanduser()
            if source_path.is_file():
                return str(source_path.parent)
            if source_path.is_dir():
                return str(source_path)

        return str(Path.home())

    def _append_log(self, message: str) -> None:
        self.log_output.appendPlainText(self._format_log_message(message))

    def _seed_initial_logs(self) -> None:
        self._append_log("[系统] GUI 已加载。")
        self._append_log("[系统] 文件、目录选择已接入。")
        self._append_log("[系统] 输入框支持拖拽与直接粘贴路径。")
        self._append_log("[系统] 已接入输入校验与语言检测。")

    def _format_log_message(self, message: str) -> str:
        timestamp = datetime.now().strftime("%H:%M:%S")
        if self._task_started_at is None:
            return f"[{timestamp}] {message}"

        elapsed = perf_counter() - self._task_started_at
        return f"[{timestamp}] [+{self._format_elapsed(elapsed)}] {message}"

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
        if self._worker is not None and self._worker.isRunning():
            return

        self._task_started_at = None
        self.source_path_edit.clear()
        self.output_dir_edit.clear()
        self.zh_to_en_radio.setChecked(True)
        self.progress_bar.setValue(0)
        self.progress_label.setText("等待开始翻译")
        self.start_button.setText("开始翻译")
        self.log_output.clear()
        self._seed_initial_logs()
        self._refresh_model_config_hint()
        self._append_log("[系统] 界面已重置，可开始新的翻译任务。")
        self.statusBar().showMessage("界面已重置")

    def _start_translation_task(
        self,
        *,
        source_path: str,
        output_dir: str,
        direction: str,
    ) -> None:
        if self._worker is not None and self._worker.isRunning():
            return

        task = TranslationTask(
            source_path=source_path,
            output_dir=output_dir,
            direction=direction,
        )
        worker = self._build_translation_worker(task)
        worker.progress_updated.connect(self._handle_progress_updated)
        worker.log_message.connect(self._append_log)
        worker.connection_checked.connect(self._handle_connection_checked)
        worker.translation_succeeded.connect(self._handle_translation_succeeded)
        worker.translation_failed.connect(self._handle_translation_failed)
        worker.finished.connect(self._handle_worker_finished)

        self._worker = worker
        self.start_button.setEnabled(False)
        self.reset_button.setEnabled(False)
        self.start_button.setText("翻译进行中")
        self.progress_bar.setValue(0)
        self.progress_label.setText("正在启动翻译任务")
        self._task_started_at = perf_counter()
        self.connection_hint_label.setText("模型状态：正在检查接口连通性")
        self.connection_hint_label.setToolTip("正在验证当前配置是否能正常调用模型接口。")
        self.statusBar().showMessage("正在执行翻译任务")
        self._append_log("[任务] 已启动后台翻译任务。")
        worker.start()

    def _build_translation_worker(self, task: TranslationTask) -> TranslationWorker:
        pipeline = DocumentTranslationPipeline(project_root=self.project_root)
        return TranslationWorker(pipeline, task, self)

    def _handle_progress_updated(self, message: str, percent: int) -> None:
        if self._task_started_at is not None:
            elapsed = perf_counter() - self._task_started_at
            display_message = f"{message}（已耗时 {self._format_elapsed(elapsed)}）"
        else:
            display_message = message

        self.progress_label.setText(display_message)
        self.progress_bar.setValue(percent)
        self.statusBar().showMessage(display_message)

    def _handle_connection_checked(self, message: str) -> None:
        self.connection_hint_label.setText(f"模型状态：接口连通 ({message})")
        self.connection_hint_label.setToolTip("已完成配置读取和接口连通性检查，可以继续执行翻译。")

    def _handle_translation_succeeded(self, result: TranslationPipelineResult) -> None:
        self.progress_bar.setValue(100)
        elapsed_seconds = result.overall_elapsed_seconds
        completion_message = f"翻译完成（总耗时 {self._format_elapsed(elapsed_seconds)}）"
        self.progress_label.setText(completion_message)
        self.statusBar().showMessage(completion_message)
        self._append_log(f"[翻译] 总片段数：{result.total_segments}")
        self._append_log(f"[翻译] 总批次数：{result.total_batches}")
        if result.total_batches > 0:
            average_batch_seconds = elapsed_seconds / result.total_batches
            self._append_log(f"[翻译] 平均每批耗时：{self._format_elapsed(average_batch_seconds)}")
        self._append_log(f"[翻译] 重试次数：{result.retry_attempts}")
        self._append_log(f"[输出] 已生成输出文件：{result.output_path}")
        QMessageBox.information(
            self,
            "翻译完成",
            f"翻译已完成，输出文件：{result.output_path}",
        )

    def _handle_translation_failed(self, stage: str, message: str) -> None:
        stage_label = self._display_stage_name(stage)
        suggestion = self._failure_suggestion(stage, message)
        self.progress_label.setText(f"{stage_label}失败")
        self.statusBar().showMessage(f"{stage_label}失败")
        if self._task_started_at is not None:
            self._append_log(f"[失败] 当前任务已耗时：{self._format_elapsed(perf_counter() - self._task_started_at)}")
        self._append_log(f"[失败] {stage_label}：{message}")
        if suggestion:
            self._append_log(f"[建议] {suggestion}")
        if stage == "model_config":
            self.connection_hint_label.setText("模型状态：配置异常")
            self.connection_hint_label.setToolTip("请先修正 .env 或 settings.json 中的模型配置。")
        elif stage == "check_connection":
            self.connection_hint_label.setText("模型状态：接口检查失败")
            self.connection_hint_label.setToolTip("配置已读取，但接口未通过连通性检查。")
        QMessageBox.critical(
            self,
            f"{stage_label}失败",
            self._build_failure_message(message, suggestion),
        )

    def _handle_worker_finished(self) -> None:
        self.start_button.setEnabled(True)
        self.reset_button.setEnabled(True)
        self.start_button.setText("开始下一次翻译")
        current_status = self.statusBar().currentMessage()
        if current_status.startswith("翻译完成"):
            self.statusBar().showMessage(f"{current_status}，可继续下一次翻译")
        elif current_status.endswith("失败"):
            self.statusBar().showMessage(f"{current_status}，可调整后重试")
        else:
            self.statusBar().showMessage("当前任务已结束，可继续下一次翻译")
        self._task_started_at = None
        if self._worker is not None:
            self._worker.deleteLater()
            self._worker = None

    def _display_stage_name(self, stage: str) -> str:
        mapping = {
            "read_source": "文件读取",
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
            "model_config": "请检查 .env 或 settings.json 中的 base_url、api_key、model 等配置。",
            "glossary": "请检查 glossary.json 是否为 UTF-8 JSON 数组，且每项都包含 source 和 target。",
            "check_connection": "请检查接口地址、API key、网络连通性，以及本机代理配置是否干扰请求。",
            "translate": "请查看日志中的批次号和片段 ID，定位是哪个批次重试或最终失败。",
            "write_output": "请检查输出目录权限、文件占用状态，以及目标文件是否已存在。",
            "unknown": "请查看日志中的最后一个失败阶段和上下文信息。",
        }
        return mapping.get(stage, "")

    def _build_failure_message(self, message: str, suggestion: str) -> str:
        if not suggestion:
            return message
        return f"{message}\n\n建议：{suggestion}"
