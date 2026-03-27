from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QAbstractItemView,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from doc_translation_tool.services import load_glossary, save_glossary


class GlossaryConfigDialog(QDialog):
    """Dialog for editing source/target glossary pairs stored in glossary.json."""

    def __init__(
        self,
        *,
        project_root: str | Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root)
        self.glossary_path = self.project_root / "glossary.json"
        self.setWindowTitle("术语配置")
        self.resize(720, 460)
        self._build_ui()
        self._load_initial_values()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        description_label = QLabel(
            "在这里维护术语表。保存后会写入当前项目目录下的 glossary.json，后续翻译任务会自动加载该文件。",
            self,
        )
        description_label.setWordWrap(True)

        self.glossary_path_label = QLabel(str(self.glossary_path), self)
        self.glossary_path_label.setStyleSheet("color: #666666;")

        self.glossary_table = QTableWidget(0, 2, self)
        self.glossary_table.setObjectName("glossaryTable")
        self.glossary_table.setHorizontalHeaderLabels(["源术语", "目标术语"])
        self.glossary_table.horizontalHeader().setStretchLastSection(True)
        self.glossary_table.verticalHeader().setVisible(False)
        self.glossary_table.setSelectionBehavior(
            QAbstractItemView.SelectionBehavior.SelectRows
        )
        self.glossary_table.setSelectionMode(
            QAbstractItemView.SelectionMode.SingleSelection
        )
        self.glossary_table.setSizePolicy(
            QSizePolicy.Policy.Expanding,
            QSizePolicy.Policy.Expanding,
        )

        self.add_entry_button = QPushButton("新增术语", self)
        self.add_entry_button.setObjectName("addGlossaryEntryButton")
        self.keep_same_button = QPushButton("保持原样", self)
        self.keep_same_button.setObjectName("keepSameGlossaryEntryButton")
        self.remove_entry_button = QPushButton("删除选中", self)
        self.remove_entry_button.setObjectName("removeGlossaryEntryButton")

        action_row = QHBoxLayout()
        action_row.setSpacing(10)
        action_row.addWidget(self.add_entry_button, 0)
        action_row.addWidget(self.keep_same_button, 0)
        action_row.addWidget(self.remove_entry_button, 0)
        action_row.addStretch(1)

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )

        self.add_entry_button.clicked.connect(self.handle_add_entry_clicked)
        self.keep_same_button.clicked.connect(self.handle_keep_same_clicked)
        self.remove_entry_button.clicked.connect(self.handle_remove_selected_clicked)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(description_label)
        layout.addWidget(QLabel("保存位置", self))
        layout.addWidget(self.glossary_path_label)
        layout.addWidget(self.glossary_table, 1)
        layout.addLayout(action_row)
        layout.addWidget(button_box)

    def _load_initial_values(self) -> None:
        for entry in load_glossary(self.glossary_path):
            self._append_entry_row(entry["source"], entry["target"])

    def _append_entry_row(self, source: str = "", target: str = "") -> None:
        row_index = self.glossary_table.rowCount()
        self.glossary_table.insertRow(row_index)
        self.glossary_table.setItem(row_index, 0, QTableWidgetItem(source))
        self.glossary_table.setItem(row_index, 1, QTableWidgetItem(target))

    def handle_add_entry_clicked(self) -> None:
        self._append_entry_row()
        last_row = self.glossary_table.rowCount() - 1
        self.glossary_table.setCurrentCell(last_row, 0)
        self.glossary_table.editItem(self.glossary_table.item(last_row, 0))

    def handle_keep_same_clicked(self) -> None:
        row_index = self._selected_row_index()
        if row_index < 0:
            return

        source = self._cell_text(row_index, 0)
        target_item = self.glossary_table.item(row_index, 1)
        if target_item is None:
            target_item = QTableWidgetItem("")
            self.glossary_table.setItem(row_index, 1, target_item)

        target_item.setText(source)

    def handle_remove_selected_clicked(self) -> None:
        selected_rows = sorted(
            {index.row() for index in self.glossary_table.selectionModel().selectedRows()},
            reverse=True,
        )
        for row_index in selected_rows:
            self.glossary_table.removeRow(row_index)

    def accept(self) -> None:
        try:
            glossary_entries = self._collect_glossary_entries()
            save_glossary(self.glossary_path, glossary_entries)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "术语配置校验失败", str(exc))
            return

        super().accept()

    def _collect_glossary_entries(self) -> list[dict[str, str]]:
        glossary_entries: list[dict[str, str]] = []
        for row_index in range(self.glossary_table.rowCount()):
            source = self._cell_text(row_index, 0)
            target = self._cell_text(row_index, 1)
            if not source and not target:
                continue
            if not source or not target:
                raise ValueError(
                    f"第 {row_index + 1} 行的源术语和目标术语都不能为空。"
                )
            glossary_entries.append(
                {
                    "source": source,
                    "target": target,
                }
            )
        return glossary_entries

    def _cell_text(self, row_index: int, column_index: int) -> str:
        item = self.glossary_table.item(row_index, column_index)
        if item is None:
            return ""
        return item.text().strip()

    def _selected_row_index(self) -> int:
        return self.glossary_table.currentRow()
