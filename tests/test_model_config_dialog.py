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
                "DOC_TRANS_TIMEOUT=90",
                "DOC_TRANS_CONNECT_TIMEOUT=12",
                "DOC_TRANS_READ_TIMEOUT=120",
                "DOC_TRANS_MAX_RETRIES=3",
                "DOC_TRANS_BATCH_SIZE=16",
                "DOC_TRANS_PARALLEL_BATCHES=4",
                "DOC_TRANS_TEMPERATURE=0.3",
                "DOC_TRANS_MAX_TOKENS=4096",
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
    assert dialog.timeout_spin.value() == 90
    assert dialog.connect_timeout_spin.value() == 12
    assert dialog.read_timeout_spin.value() == 120
    assert dialog.max_retries_spin.value() == 3
    assert dialog.batch_size_spin.value() == 16
    assert dialog.parallel_batches_spin.value() == 4
    assert dialog.temperature_spin.value() == 0.3
    assert dialog.max_tokens_edit.text() == "4096"
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
    dialog.timeout_spin.setValue(75)
    dialog.connect_timeout_spin.setValue(15)
    dialog.read_timeout_spin.setValue(95)
    dialog.max_retries_spin.setValue(4)
    dialog.batch_size_spin.setValue(12)
    dialog.parallel_batches_spin.setValue(5)
    dialog.temperature_spin.setValue(0.4)
    dialog.max_tokens_edit.setText("2048")

    dialog.accept()

    settings = load_app_settings(tmp_path)
    assert settings.llm.base_url == "https://saved.example/v1"
    assert settings.llm.api_key == "saved-secret"
    assert settings.llm.model == "saved-model"
    assert settings.llm.timeout == 75
    assert settings.llm.connect_timeout == 15
    assert settings.llm.read_timeout == 95
    assert settings.llm.max_retries == 4
    assert settings.llm.batch_size == 12
    assert settings.llm.parallel_batches == 5
    assert settings.llm.temperature == 0.4
    assert settings.llm.max_tokens == 2048
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_uses_settings_defaults_for_advanced_values(
    tmp_path: Path,
    qapp,
) -> None:
    (tmp_path / "settings.json").write_text(
        (
            "{\n"
            '  "llm": {\n'
            '    "timeout": 88,\n'
            '    "connect_timeout": 14,\n'
            '    "read_timeout": 99,\n'
            '    "max_retries": 5,\n'
            '    "batch_size": 10,\n'
            '    "parallel_batches": 6,\n'
            '    "temperature": 0.6,\n'
            '    "max_tokens": 3072\n'
            "  }\n"
            "}\n"
        ),
        encoding="utf-8",
    )

    dialog = ModelConfigDialog(project_root=tmp_path)

    assert dialog.timeout_spin.value() == 88
    assert dialog.connect_timeout_spin.value() == 14
    assert dialog.read_timeout_spin.value() == 99
    assert dialog.max_retries_spin.value() == 5
    assert dialog.batch_size_spin.value() == 10
    assert dialog.parallel_batches_spin.value() == 6
    assert dialog.temperature_spin.value() == 0.6
    assert dialog.max_tokens_edit.text() == "3072"
    dialog.close()
    dialog.deleteLater()


def test_model_config_dialog_build_test_settings_validates_max_tokens(
    tmp_path: Path,
    qapp,
) -> None:
    dialog = ModelConfigDialog(project_root=tmp_path)
    dialog.provider_combo.setCurrentIndex(dialog.provider_combo.findData("mock"))
    dialog.model_edit.setText("mock-model")
    dialog.max_tokens_edit.setText("not-a-number")

    try:
        dialog._build_test_settings()
    except ValueError as exc:
        assert str(exc) == "Max Tokens 必须为整数。"
    else:
        raise AssertionError("Expected ValueError for invalid max_tokens")

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
