from pathlib import Path

from pytest import MonkeyPatch
from PySide6.QtWidgets import QLineEdit

from doc_translation_tool.config import load_app_settings
from doc_translation_tool.ui.model_config_dialog import ModelConfigDialog


def test_model_config_dialog_loads_existing_env_values(tmp_path: Path, qapp) -> None:
    (tmp_path / ".env").write_text(
        "\n".join(
            [
                "DOC_TRANS_PROVIDER=openai_compatible",
                "DOC_TRANS_API_FORMAT=anthropic",
                "DOC_TRANS_ANTHROPIC_VERSION=2023-06-01",
                "DOC_TRANS_BASE_URL=https://dialog.example/v1",
                "DOC_TRANS_API_KEY=dialog-secret",
                "DOC_TRANS_MODEL=dialog-model",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    dialog = ModelConfigDialog(project_root=tmp_path)

    assert dialog.provider_combo.currentData() == "openai_compatible"
    assert dialog.api_format_combo.currentData() == "anthropic"
    assert dialog.base_url_edit.text() == "https://dialog.example/v1"
    assert dialog.api_key_edit.text() == "dialog-secret"
    assert dialog.model_edit.text() == "dialog-model"
    assert dialog.anthropic_version_edit.text() == "2023-06-01"
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_accept_saves_values_to_env(tmp_path: Path, qapp) -> None:
    dialog = ModelConfigDialog(project_root=tmp_path)
    dialog.provider_combo.setCurrentIndex(
        dialog.provider_combo.findData("openai_compatible")
    )
    dialog.api_format_combo.setCurrentIndex(dialog.api_format_combo.findData("openai"))
    dialog.base_url_edit.setText("https://saved.example/v1")
    dialog.api_key_edit.setText("saved-secret")
    dialog.model_edit.setText("saved-model")
    dialog.anthropic_version_edit.setText("2023-06-01")

    dialog.accept()

    settings = load_app_settings(tmp_path)
    assert settings.llm.base_url == "https://saved.example/v1"
    assert settings.llm.api_key == "saved-secret"
    assert settings.llm.model == "saved-model"
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_toggles_api_key_visibility(tmp_path: Path, qapp) -> None:
    dialog = ModelConfigDialog(project_root=tmp_path)

    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.PasswordEchoOnEdit
    dialog.toggle_api_key_visibility_button.setChecked(True)
    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.Normal
    assert dialog.toggle_api_key_visibility_button.text() == "隐藏"

    dialog.toggle_api_key_visibility_button.setChecked(False)
    assert dialog.api_key_edit.echoMode() == QLineEdit.EchoMode.PasswordEchoOnEdit
    assert dialog.toggle_api_key_visibility_button.text() == "显示"
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_test_connection_updates_success_status(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    class FakeSignal:
        def __init__(self) -> None:
            self._callbacks = []

        def connect(self, callback) -> None:
            self._callbacks.append(callback)

        def emit(self, *args) -> None:
            for callback in self._callbacks:
                callback(*args)

    class FakeWorker:
        def __init__(self) -> None:
            self.succeeded = FakeSignal()
            self.failed = FakeSignal()
            self.finished = FakeSignal()

        def start(self) -> None:
            self.succeeded.emit("OK")
            self.finished.emit()

        def isRunning(self) -> bool:
            return False

        def deleteLater(self) -> None:
            return None

    dialog = ModelConfigDialog(project_root=tmp_path)
    dialog.provider_combo.setCurrentIndex(dialog.provider_combo.findData("mock"))
    dialog.model_edit.setText("mock-model")
    monkeypatch.setattr(
        dialog,
        "_build_connection_test_worker",
        lambda _settings: FakeWorker(),
    )

    dialog.handle_test_connection_clicked()

    assert dialog.connection_test_status_label.text() == "连接成功：当前配置可用。\n接口响应：OK"
    assert dialog.connection_test_status_label.toolTip() == "OK"
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_test_connection_updates_failure_status(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
    qapp,
) -> None:
    class FakeSignal:
        def __init__(self) -> None:
            self._callbacks = []

        def connect(self, callback) -> None:
            self._callbacks.append(callback)

        def emit(self, *args) -> None:
            for callback in self._callbacks:
                callback(*args)

    class FakeWorker:
        def __init__(self) -> None:
            self.succeeded = FakeSignal()
            self.failed = FakeSignal()
            self.finished = FakeSignal()

        def start(self) -> None:
            self.failed.emit("network error")
            self.finished.emit()

        def isRunning(self) -> bool:
            return False

        def deleteLater(self) -> None:
            return None

    dialog = ModelConfigDialog(project_root=tmp_path)
    dialog.provider_combo.setCurrentIndex(dialog.provider_combo.findData("mock"))
    dialog.model_edit.setText("mock-model")
    monkeypatch.setattr(
        dialog,
        "_build_connection_test_worker",
        lambda _settings: FakeWorker(),
    )

    dialog.handle_test_connection_clicked()

    assert "连接失败：未识别的连接错误" in dialog.connection_test_status_label.text()
    assert "原始错误：network error" in dialog.connection_test_status_label.text()
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_classifies_auth_failure(tmp_path: Path, qapp) -> None:
    dialog = ModelConfigDialog(project_root=tmp_path)

    dialog._handle_connection_test_failed(
        "Model request failed: HTTP 401 Unauthorized. Detail: invalid api key"
    )

    status_text = dialog.connection_test_status_label.text()
    assert "连接失败：鉴权失败" in status_text
    assert "API Key" in status_text
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_classifies_rate_limit_failure(tmp_path: Path, qapp) -> None:
    dialog = ModelConfigDialog(project_root=tmp_path)

    dialog._handle_connection_test_failed(
        "Model request rate limited: HTTP 429 Too Many Requests."
    )

    status_text = dialog.connection_test_status_label.text()
    assert "连接失败：接口被限流" in status_text
    assert "降低并发" in status_text
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_classifies_endpoint_failure(tmp_path: Path, qapp) -> None:
    dialog = ModelConfigDialog(project_root=tmp_path)

    dialog._handle_connection_test_failed(
        "Model request failed: HTTP 404 Not Found. POST /chat/completions"
    )

    status_text = dialog.connection_test_status_label.text()
    assert "连接失败：接口地址可能不正确" in status_text
    assert "Base URL" in status_text
    dialog.close()
    dialog.deleteLater()
