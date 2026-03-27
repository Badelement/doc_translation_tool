import json
from pathlib import Path

from pytest import MonkeyPatch
from PySide6.QtWidgets import QTableWidgetItem

from doc_translation_tool.ui.glossary_config_dialog import GlossaryConfigDialog


def test_glossary_config_dialog_loads_existing_glossary(tmp_path: Path, qapp) -> None:
    (tmp_path / "glossary.json").write_text(
        json.dumps(
            [
                {"source": "远程音效", "target": "remote sound effect"},
                {"source": "Android13", "target": "Android13"},
            ],
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    dialog = GlossaryConfigDialog(project_root=tmp_path)

    assert dialog.glossary_table.rowCount() == 2
    assert dialog.glossary_table.item(0, 0).text() == "远程音效"
    assert dialog.glossary_table.item(0, 1).text() == "remote sound effect"
    dialog.close()
    dialog.deleteLater()


def test_glossary_config_dialog_accept_saves_values_to_glossary_json(
    tmp_path: Path,
    qapp,
) -> None:
    dialog = GlossaryConfigDialog(project_root=tmp_path)
    dialog.handle_add_entry_clicked()
    dialog.glossary_table.setItem(0, 0, QTableWidgetItem("远程音效"))
    dialog.glossary_table.setItem(0, 1, QTableWidgetItem("remote sound effect"))
    dialog.handle_add_entry_clicked()
    dialog.glossary_table.setItem(1, 0, QTableWidgetItem("Android13"))
    dialog.glossary_table.setItem(1, 1, QTableWidgetItem("Android13"))

    dialog.accept()

    assert json.loads((tmp_path / "glossary.json").read_text(encoding="utf-8")) == [
        {"source": "远程音效", "target": "remote sound effect"},
        {"source": "Android13", "target": "Android13"},
    ]
    dialog.close()
    dialog.deleteLater()


def test_glossary_config_dialog_remove_selected_row(tmp_path: Path, qapp) -> None:
    dialog = GlossaryConfigDialog(project_root=tmp_path)
    dialog.handle_add_entry_clicked()
    dialog.handle_add_entry_clicked()
    dialog.glossary_table.selectRow(0)

    dialog.handle_remove_selected_clicked()

    assert dialog.glossary_table.rowCount() == 1
    dialog.close()
    dialog.deleteLater()


def test_glossary_config_dialog_keep_same_copies_source_to_target(
    tmp_path: Path,
    qapp,
) -> None:
    dialog = GlossaryConfigDialog(project_root=tmp_path)
    dialog.handle_add_entry_clicked()
    dialog.glossary_table.setItem(0, 0, QTableWidgetItem("Android13"))
    dialog.glossary_table.selectRow(0)

    dialog.handle_keep_same_clicked()

    assert dialog.glossary_table.item(0, 1).text() == "Android13"
    dialog.close()
    dialog.deleteLater()


def test_glossary_config_dialog_keep_same_without_selection_is_noop(
    tmp_path: Path,
    qapp,
) -> None:
    dialog = GlossaryConfigDialog(project_root=tmp_path)
    dialog.handle_add_entry_clicked()
    dialog.glossary_table.setItem(0, 0, QTableWidgetItem("Android13"))
    dialog.glossary_table.clearSelection()
    dialog.glossary_table.setCurrentCell(-1, -1)

    dialog.handle_keep_same_clicked()

    assert dialog.glossary_table.item(0, 1).text() == ""
    dialog.close()
    dialog.deleteLater()


def test_glossary_config_dialog_accept_rejects_partial_rows(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    captured: dict[str, str] = {}

    def fake_warning(_parent, title: str, message: str) -> None:
        captured["title"] = title
        captured["message"] = message

    monkeypatch.setattr(
        "doc_translation_tool.ui.glossary_config_dialog.QMessageBox.warning",
        fake_warning,
    )

    dialog = GlossaryConfigDialog(project_root=tmp_path)
    dialog.handle_add_entry_clicked()
    dialog.glossary_table.setItem(0, 0, QTableWidgetItem("Only source"))

    dialog.accept()

    assert captured["title"] == "术语配置校验失败"
    assert "第 1 行" in captured["message"]
    assert (tmp_path / "glossary.json").exists() is False
    dialog.close()
    dialog.deleteLater()
