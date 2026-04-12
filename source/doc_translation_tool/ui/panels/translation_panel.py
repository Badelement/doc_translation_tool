"""Single file translation panel component."""

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

from doc_translation_tool.document_types import (
    source_file_dialog_filter,
    source_path_placeholder_text,
)
from doc_translation_tool.ui.path_line_edit import PathLineEdit

if TYPE_CHECKING:
    pass


class TranslationPanel(QWidget):
    """Panel for single file translation configuration."""

    # Signals
    source_path_changed = Signal(str)
    output_directory_changed = Signal(str)
    direction_changed = Signal(str)
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

        source_label = QLabel("目标翻译文件", group)
        output_label = QLabel("生成目录", group)

        self.source_path_edit = PathLineEdit(
            path_kind="document_file",
            on_path_received=self._handle_source_path_received,
            parent=group,
        )
        self.source_path_edit.setPlaceholderText(source_path_placeholder_text())

        self.output_dir_edit = PathLineEdit(
            path_kind="directory",
            on_path_received=self._handle_output_directory_received,
            parent=group,
        )
        self.output_dir_edit.setPlaceholderText("请选择、拖入或粘贴输出目录路径")

        self.browse_source_button = QPushButton("浏览文件", group)
        self.browse_output_button = QPushButton("浏览目录", group)

        layout.addWidget(source_label, 0, 0)
        layout.addWidget(self.source_path_edit, 0, 1)
        layout.addWidget(self.browse_source_button, 0, 2)
        layout.addWidget(output_label, 1, 0)
        layout.addWidget(self.output_dir_edit, 1, 1)
        layout.addWidget(self.browse_output_button, 1, 2)
        layout.setColumnStretch(1, 1)
        return group

    def _create_direction_group(self) -> QGroupBox:
        self.direction_group = QGroupBox("翻译方向", self)
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

        radio_row.addWidget(self.zh_to_en_radio)
        radio_row.addWidget(self.en_to_zh_radio)
        radio_row.addStretch(1)
        layout.addLayout(radio_row)

        # Create a hidden hint label for compatibility with batch mode
        self.direction_hint_label = QLabel(self.direction_group)
        self.direction_hint_label.hide()

        return self.direction_group

    def _connect_signals(self) -> None:
        self.browse_source_button.clicked.connect(self._select_source_file)
        self.browse_output_button.clicked.connect(self._select_output_directory)
        self.source_path_edit.editingFinished.connect(self._commit_source_path_text)
        self.output_dir_edit.editingFinished.connect(self._commit_output_directory_text)
        self.zh_to_en_radio.toggled.connect(self._handle_direction_toggled)
        self.en_to_zh_radio.toggled.connect(self._handle_direction_toggled)

    def _select_source_file(self) -> None:
        suggested_dir = self._suggest_source_file_directory()
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "选择目标翻译文件",
            suggested_dir,
            source_file_dialog_filter(),
        )
        if selected_path:
            self._handle_source_path_received(selected_path)

    def _select_output_directory(self) -> None:
        suggested_dir = self._suggest_output_directory()
        selected_directory = QFileDialog.getExistingDirectory(
            self,
            "选择输出目录",
            suggested_dir,
        )
        if selected_directory:
            self._handle_output_directory_received(selected_directory)

    def _handle_source_path_received(self, source_path: str) -> None:
        self.source_path_edit.setText(source_path)
        self.source_path_changed.emit(source_path)

    def _handle_output_directory_received(self, output_directory: str) -> None:
        self.output_dir_edit.setText(output_directory)
        self.output_directory_changed.emit(output_directory)

    def _commit_source_path_text(self) -> None:
        text = self.source_path_edit.text().strip()
        if text:
            self.source_path_changed.emit(text)

    def _commit_output_directory_text(self) -> None:
        text = self.output_dir_edit.text().strip()
        if text:
            self.output_directory_changed.emit(text)

    def _handle_direction_toggled(self, checked: bool) -> None:
        if not checked:
            return
        direction = self.get_direction()
        self.direction_changed.emit(direction)

    def _suggest_source_file_directory(self) -> str:
        source_text = self.source_path_edit.text().strip()
        if source_text:
            source_path = Path(source_text)
            if source_path.is_file():
                return str(source_path.parent)
            if source_path.is_dir():
                return str(source_path)
        return str(Path.home())

    def _suggest_output_directory(self) -> str:
        output_text = self.output_dir_edit.text().strip()
        if output_text:
            output_path = Path(output_text)
            if output_path.is_dir():
                return str(output_path)
            if output_path.parent.is_dir():
                return str(output_path.parent)

        source_text = self.source_path_edit.text().strip()
        if source_text:
            source_path = Path(source_text)
            if source_path.is_file() and source_path.parent.is_dir():
                return str(source_path.parent)
            if source_path.is_dir():
                return str(source_path)

        return str(Path.home())

    # Public API
    def get_source_path(self) -> str:
        return self.source_path_edit.text().strip()

    def set_source_path(self, source_path: str) -> None:
        self.source_path_edit.setText(source_path)

    def get_output_directory(self) -> str:
        return self.output_dir_edit.text().strip()

    def set_output_directory(self, output_directory: str) -> None:
        self.output_dir_edit.setText(output_directory)

    def get_direction(self) -> str:
        return "zh_to_en" if self.zh_to_en_radio.isChecked() else "en_to_zh"

    def set_direction(self, direction: str) -> None:
        if direction == "zh_to_en":
            self.zh_to_en_radio.setChecked(True)
        else:
            self.en_to_zh_radio.setChecked(True)

    def clear(self) -> None:
        """Clear all input fields."""
        self.source_path_edit.clear()
        self.output_dir_edit.clear()
