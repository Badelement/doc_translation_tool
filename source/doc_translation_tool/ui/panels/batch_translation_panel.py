"""Batch translation panel component."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QButtonGroup,
    QFileDialog,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from doc_translation_tool.ui.path_line_edit import PathLineEdit

if TYPE_CHECKING:
    pass


class BatchTranslationPanel(QWidget):
    """Panel for batch translation configuration."""

    # Signals
    source_directory_changed = Signal(str)
    output_directory_changed = Signal(str)
    default_direction_changed = Signal(str)
    start_requested = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build_ui()
        self._connect_signals()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(16)

        layout.addWidget(self._create_path_group())
        layout.addWidget(self._create_direction_group())

    def _create_path_group(self) -> QGroupBox:
        group = QGroupBox("路径设置", self)
        layout = QGridLayout(group)
        layout.setHorizontalSpacing(12)
        layout.setVerticalSpacing(12)

        self.source_path_label = QLabel("源目录", group)
        output_label = QLabel("生成目录", group)

        self.source_dir_edit = PathLineEdit(
            path_kind="directory",
            on_path_received=self._handle_source_directory_received,
            parent=group,
        )
        self.source_dir_edit.setPlaceholderText("请选择、拖入或粘贴源目录路径")

        self.output_dir_edit = PathLineEdit(
            path_kind="directory",
            on_path_received=self._handle_output_directory_received,
            parent=group,
        )
        self.output_dir_edit.setPlaceholderText("请选择、拖入或粘贴输出目录路径")

        self.browse_source_button = QPushButton("浏览目录", group)
        self.clear_source_button = QPushButton("清空路径", group)
        self.browse_output_button = QPushButton("浏览目录", group)

        layout.addWidget(self.source_path_label, 0, 0)
        layout.addWidget(self.source_dir_edit, 0, 1)
        layout.addWidget(self.browse_source_button, 0, 2)
        layout.addWidget(self.clear_source_button, 0, 3)
        layout.addWidget(output_label, 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1, 1, 2)
        layout.addWidget(self.browse_output_button, 1, 3)
        layout.setColumnStretch(1, 1)
        return group

    def _create_direction_group(self) -> QGroupBox:
        self.direction_group = QGroupBox("默认翻译方向", self)
        layout = QVBoxLayout(self.direction_group)
        layout.setContentsMargins(16, 14, 16, 14)
        layout.setSpacing(10)

        radio_row = QHBoxLayout()
        radio_row.setSpacing(24)

        self.zh_to_en_radio = QRadioButton("中译英", self.direction_group)
        self.en_to_zh_radio = QRadioButton("英译中", self.direction_group)
        self.zh_to_en_radio.setChecked(True)

        self.direction_button_group = QButtonGroup(self.direction_group)
        self.direction_button_group.addButton(self.zh_to_en_radio)
        self.direction_button_group.addButton(self.en_to_zh_radio)

        self.direction_hint_label = QLabel(
            "目录批量会自动按文件识别方向；只有未确定文件会使用这里的默认方向。",
            self.direction_group,
        )
        self.direction_hint_label.setWordWrap(True)
        self.direction_hint_label.setStyleSheet("color: #666666;")

        radio_row.addWidget(self.zh_to_en_radio)
        radio_row.addWidget(self.en_to_zh_radio)
        radio_row.addStretch(1)
        layout.addLayout(radio_row)
        layout.addWidget(self.direction_hint_label)
        return self.direction_group

    def _connect_signals(self) -> None:
        self.browse_source_button.clicked.connect(self._select_source_directory)
        self.clear_source_button.clicked.connect(self._clear_source_directory)
        self.browse_output_button.clicked.connect(self._select_output_directory)
        self.source_dir_edit.editingFinished.connect(self._commit_source_directory_text)
        self.output_dir_edit.editingFinished.connect(self._commit_output_directory_text)
        self.zh_to_en_radio.toggled.connect(self._handle_direction_toggled)
        self.en_to_zh_radio.toggled.connect(self._handle_direction_toggled)

    def _select_source_directory(self) -> None:
        suggested_dir = self._suggest_source_directory()
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "选择源目录",
            suggested_dir,
        )
        if selected_directory:
            self._handle_source_directory_received(selected_directory)

    def _select_output_directory(self) -> None:
        suggested_dir = self._suggest_output_directory()
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            suggested_dir,
        )
        if selected_directory:
            self._handle_output_directory_received(selected_directory)

    def _clear_source_directory(self) -> None:
        self.source_dir_edit.clear()
        self.source_directory_changed.emit("")

    def _handle_source_directory_received(self, source_directory: str) -> None:
        self.source_dir_edit.setText(source_directory)
        self.source_directory_changed.emit(source_directory)

    def _handle_output_directory_received(self, output_directory: str) -> None:
        self.output_dir_edit.setText(output_directory)
        self.output_directory_changed.emit(output_directory)

    def _commit_source_directory_text(self) -> None:
        text = self.source_dir_edit.text().strip()
        if text:
            self.source_directory_changed.emit(text)

    def _commit_output_directory_text(self) -> None:
        text = self.output_dir_edit.text().strip()
        if text:
            self.output_directory_changed.emit(text)

    def _handle_direction_toggled(self, checked: bool) -> None:
        if not checked:
            return
        direction = self.get_default_direction()
        self.default_direction_changed.emit(direction)

    def _suggest_source_directory(self) -> str:
        source_text = self.source_dir_edit.text().strip()
        if source_text:
            source_path = Path(source_text)
            if source_path.is_dir():
                return str(source_path)
            if source_path.parent.is_dir():
                return str(source_path.parent)
        return str(Path.home())

    def _suggest_output_directory(self) -> str:
        output_text = self.output_dir_edit.text().strip()
        if output_text:
            output_path = Path(output_text)
            if output_path.is_dir():
                return str(output_path)
            if output_path.parent.is_dir():
                return str(output_path.parent)

        source_text = self.source_dir_edit.text().strip()
        if source_text:
            source_path = Path(source_text)
            if source_path.is_dir():
                return str(source_path)

        return str(Path.home())

    # Public API
    def get_source_directory(self) -> str:
        return self.source_dir_edit.text().strip()

    def set_source_directory(self, source_directory: str) -> None:
        self.source_dir_edit.setText(source_directory)

    def get_output_directory(self) -> str:
        return self.output_dir_edit.text().strip()

    def set_output_directory(self, output_directory: str) -> None:
        self.output_dir_edit.setText(output_directory)

    def get_default_direction(self) -> str:
        return "zh_to_en" if self.zh_to_en_radio.isChecked() else "en_to_zh"

    def set_default_direction(self, direction: str) -> None:
        if direction == "zh_to_en":
            self.zh_to_en_radio.setChecked(True)
        else:
            self.en_to_zh_radio.setChecked(True)

    def clear(self) -> None:
        """Clear all input fields."""
        self.source_dir_edit.clear()
        self.output_dir_edit.clear()
