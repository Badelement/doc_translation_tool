"""Progress and log display components."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QProgressBar,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


class ProgressGroup(QWidget):
    """Progress display component."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("任务状态", self)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(16, 14, 16, 16)
        group_layout.setSpacing(10)

        self.progress_label = QLabel("等待开始翻译", group)
        self.progress_bar = QProgressBar(group)
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFormat("%p%")

        group_layout.addWidget(self.progress_label)
        group_layout.addWidget(self.progress_bar)

        layout.addWidget(group)

    def set_progress(self, message: str, percent: int) -> None:
        """Update progress display."""
        self.progress_label.setText(message)
        self.progress_bar.setValue(percent)

    def reset(self) -> None:
        """Reset to initial state."""
        self.progress_label.setText("等待开始翻译")
        self.progress_bar.setValue(0)


class LogGroup(QWidget):
    """Log display component."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        group = QGroupBox("任务摘要", self)
        group_layout = QVBoxLayout(group)
        group_layout.setContentsMargins(16, 14, 16, 16)

        self.log_output = QPlainTextEdit(group)
        self.log_output.setReadOnly(True)
        self.log_output.setObjectName("logOutput")
        self.log_output.setPlaceholderText("本次翻译的简要状态会显示在这里。")
        self.log_output.setMaximumBlockCount(8)
        self.log_output.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Fixed,
        )
        self.log_output.setFixedHeight(110)

        group_layout.addWidget(self.log_output)
        layout.addWidget(group)

    def append_line(self, message: str) -> None:
        """Append a line to the log."""
        self.log_output.appendPlainText(message)

    def clear(self) -> None:
        """Clear the log."""
        self.log_output.clear()


class ActionBar(QWidget):
    """Action buttons and status bar."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self) -> None:
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(12)

        self.connection_hint_label = QLabel("模型状态：未检查", self)
        self.connection_hint_label.setAlignment(
            Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft
        )

        self.start_button = QPushButton("开始翻译", self)
        self.start_button.setObjectName("startButton")
        self.start_button.setMinimumHeight(40)

        self.open_model_config_button = QPushButton("模型配置", self)
        self.open_model_config_button.setObjectName("openModelConfigButton")
        self.open_model_config_button.setMinimumHeight(40)

        self.open_glossary_config_button = QPushButton("术语配置", self)
        self.open_glossary_config_button.setObjectName("openGlossaryConfigButton")
        self.open_glossary_config_button.setMinimumHeight(40)

        self.reset_button = QPushButton("重置界面", self)
        self.reset_button.setObjectName("resetButton")
        self.reset_button.setMinimumHeight(40)

        self.open_task_log_button = QPushButton("查看详细日志", self)
        self.open_task_log_button.setObjectName("openTaskLogButton")
        self.open_task_log_button.setMinimumHeight(40)
        self.open_task_log_button.setEnabled(False)
        self.open_task_log_button.setToolTip("当前任务生成日志后，可在这里查看完整内容。")

        layout.addWidget(self.connection_hint_label, 1)
        layout.addWidget(self.open_model_config_button, 0)
        layout.addWidget(self.open_glossary_config_button, 0)
        layout.addWidget(self.open_task_log_button, 0)
        layout.addWidget(self.reset_button, 0)
        layout.addWidget(self.start_button, 0)

    def set_connection_hint(self, text: str, tooltip: str = "") -> None:
        """Update connection status hint."""
        self.connection_hint_label.setText(text)
        if tooltip:
            self.connection_hint_label.setToolTip(tooltip)

    def set_action_buttons_enabled(self, enabled: bool) -> None:
        """Enable or disable action buttons."""
        self.start_button.setEnabled(enabled)
        self.reset_button.setEnabled(enabled)
        self.open_model_config_button.setEnabled(enabled)
        self.open_glossary_config_button.setEnabled(enabled)

    def set_log_button_enabled(self, enabled: bool) -> None:
        """Enable or disable log viewer button."""
        self.open_task_log_button.setEnabled(enabled)
