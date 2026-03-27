from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDoubleSpinBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from doc_translation_tool.config import (
    LLMSettings,
    load_app_settings,
    load_env_file_values,
    save_env_file_values,
)
from doc_translation_tool.llm import LLMClientError, create_llm_client


class ConnectionTestWorker(QThread):
    """Run model connectivity checks without blocking the dialog UI."""

    succeeded = Signal(str)
    failed = Signal(str)

    def __init__(
        self,
        *,
        settings: LLMSettings,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.settings = settings

    def run(self) -> None:
        client = None
        try:
            client = create_llm_client(self.settings)
            message = client.check_connection()
        except (LLMClientError, ValueError) as exc:
            self.failed.emit(str(exc))
            return
        finally:
            if client is not None:
                client.close()

        self.succeeded.emit(message)


class ModelConfigDialog(QDialog):
    """Dialog for editing model connection settings stored in .env."""

    def __init__(
        self,
        *,
        project_root: str | Path,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_root = Path(project_root)
        self._connection_worker: ConnectionTestWorker | None = None
        self.setWindowTitle("模型配置")
        self.resize(560, 360)
        self._build_ui()
        self._load_initial_values()
        self._sync_field_state()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 18)
        layout.setSpacing(14)

        description_label = QLabel(
            "这里可以维护模型接口地址、API Key 和模型名称。保存后会写入当前项目目录下的 .env。",
            self,
        )
        description_label.setWordWrap(True)

        priority_label = QLabel(
            "说明：运行时环境变量的优先级仍高于 .env；在常规桌面使用场景下，保存后的配置会直接用于后续翻译任务。",
            self,
        )
        priority_label.setWordWrap(True)
        priority_label.setStyleSheet("color: #666666;")

        basic_group = QGroupBox("基础配置", self)
        basic_form = QFormLayout(basic_group)
        basic_form.setContentsMargins(14, 14, 14, 14)
        basic_form.setSpacing(10)

        self.provider_combo = QComboBox(basic_group)
        self.provider_combo.addItem("OpenAI Compatible", "openai_compatible")
        self.provider_combo.addItem("Compatible", "compatible")
        self.provider_combo.addItem("Anthropic Compatible", "anthropic_compatible")
        self.provider_combo.addItem("Mock", "mock")

        self.api_format_combo = QComboBox(basic_group)
        self.api_format_combo.addItem("OpenAI", "openai")
        self.api_format_combo.addItem("Anthropic", "anthropic")

        self.base_url_edit = QLineEdit(basic_group)
        self.base_url_edit.setObjectName("baseUrlEdit")
        self.base_url_edit.setPlaceholderText("https://example.internal/api/v1")

        self.api_key_edit = QLineEdit(basic_group)
        self.api_key_edit.setObjectName("apiKeyEdit")
        self.api_key_edit.setEchoMode(QLineEdit.EchoMode.PasswordEchoOnEdit)
        self.api_key_edit.setPlaceholderText("输入 API Key")
        self.toggle_api_key_visibility_button = QPushButton("显示", basic_group)
        self.toggle_api_key_visibility_button.setObjectName(
            "toggleApiKeyVisibilityButton"
        )
        self.toggle_api_key_visibility_button.setCheckable(True)
        api_key_row = QWidget(basic_group)
        api_key_layout = QHBoxLayout(api_key_row)
        api_key_layout.setContentsMargins(0, 0, 0, 0)
        api_key_layout.setSpacing(8)
        api_key_layout.addWidget(self.api_key_edit, 1)
        api_key_layout.addWidget(self.toggle_api_key_visibility_button, 0)

        self.model_edit = QLineEdit(basic_group)
        self.model_edit.setObjectName("modelEdit")
        self.model_edit.setPlaceholderText(
            "例如：qwen3-max、gpt-4.1、claude-compatible"
        )

        basic_form.addRow("Provider", self.provider_combo)
        basic_form.addRow("API 格式", self.api_format_combo)
        basic_form.addRow("Base URL", self.base_url_edit)
        basic_form.addRow("API Key", api_key_row)
        basic_form.addRow("模型名称", self.model_edit)

        advanced_group = QGroupBox("兼容配置", self)
        advanced_form = QFormLayout(advanced_group)
        advanced_form.setContentsMargins(14, 14, 14, 14)
        advanced_form.setSpacing(10)

        self.anthropic_version_edit = QLineEdit(advanced_group)
        self.anthropic_version_edit.setObjectName("anthropicVersionEdit")
        self.anthropic_version_edit.setPlaceholderText("2023-06-01")
        advanced_form.addRow("Anthropic Version", self.anthropic_version_edit)

        tuning_group = QGroupBox("高级参数", self)
        tuning_form = QFormLayout(tuning_group)
        tuning_form.setContentsMargins(14, 14, 14, 14)
        tuning_form.setSpacing(10)

        self.timeout_spin = QSpinBox(tuning_group)
        self.timeout_spin.setObjectName("timeoutSpin")
        self.timeout_spin.setRange(1, 3600)
        self.timeout_spin.setSuffix(" s")

        self.connect_timeout_spin = QSpinBox(tuning_group)
        self.connect_timeout_spin.setObjectName("connectTimeoutSpin")
        self.connect_timeout_spin.setRange(1, 3600)
        self.connect_timeout_spin.setSuffix(" s")

        self.read_timeout_spin = QSpinBox(tuning_group)
        self.read_timeout_spin.setObjectName("readTimeoutSpin")
        self.read_timeout_spin.setRange(1, 3600)
        self.read_timeout_spin.setSuffix(" s")

        self.max_retries_spin = QSpinBox(tuning_group)
        self.max_retries_spin.setObjectName("maxRetriesSpin")
        self.max_retries_spin.setRange(0, 20)

        self.batch_size_spin = QSpinBox(tuning_group)
        self.batch_size_spin.setObjectName("batchSizeSpin")
        self.batch_size_spin.setRange(1, 512)

        self.parallel_batches_spin = QSpinBox(tuning_group)
        self.parallel_batches_spin.setObjectName("parallelBatchesSpin")
        self.parallel_batches_spin.setRange(1, 64)

        self.temperature_spin = QDoubleSpinBox(tuning_group)
        self.temperature_spin.setObjectName("temperatureSpin")
        self.temperature_spin.setRange(0.0, 2.0)
        self.temperature_spin.setDecimals(2)
        self.temperature_spin.setSingleStep(0.1)

        self.max_tokens_edit = QLineEdit(tuning_group)
        self.max_tokens_edit.setObjectName("maxTokensEdit")
        self.max_tokens_edit.setPlaceholderText("留空表示使用服务默认值")

        tuning_form.addRow("Timeout", self.timeout_spin)
        tuning_form.addRow("Connect Timeout", self.connect_timeout_spin)
        tuning_form.addRow("Read Timeout", self.read_timeout_spin)
        tuning_form.addRow("Max Retries", self.max_retries_spin)
        tuning_form.addRow("Batch Size", self.batch_size_spin)
        tuning_form.addRow("Parallel Batches", self.parallel_batches_spin)
        tuning_form.addRow("Temperature", self.temperature_spin)
        tuning_form.addRow("Max Tokens", self.max_tokens_edit)

        self.env_path_label = QLabel(str(self.project_root / ".env"), self)
        self.env_path_label.setStyleSheet("color: #666666;")

        self.connection_test_status_label = QLabel("尚未测试当前配置。", self)
        self.connection_test_status_label.setWordWrap(True)
        self.connection_test_status_label.setStyleSheet("color: #666666;")

        self.test_connection_button = QPushButton("测试连接", self)
        self.test_connection_button.setObjectName("testConnectionButton")

        button_box = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Save
            | QDialogButtonBox.StandardButton.Cancel,
            parent=self,
        )
        self.save_button = button_box.button(QDialogButtonBox.StandardButton.Save)

        self.provider_combo.currentIndexChanged.connect(self._sync_field_state)
        self.api_format_combo.currentIndexChanged.connect(self._sync_field_state)
        self.toggle_api_key_visibility_button.toggled.connect(
            self._handle_api_key_visibility_toggled
        )
        self.test_connection_button.clicked.connect(self.handle_test_connection_clicked)
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)

        layout.addWidget(description_label)
        layout.addWidget(priority_label)
        layout.addWidget(basic_group)
        layout.addWidget(advanced_group)
        layout.addWidget(tuning_group)
        layout.addWidget(QLabel("保存位置", self))
        layout.addWidget(self.env_path_label)
        layout.addWidget(self.connection_test_status_label)
        layout.addWidget(self.test_connection_button)
        layout.addWidget(button_box)

    def _load_initial_values(self) -> None:
        settings = load_app_settings(self.project_root)
        env_values = load_env_file_values(self.project_root)

        self._set_combo_data(
            self.provider_combo,
            env_values.get("DOC_TRANS_PROVIDER", settings.llm.provider),
        )
        self._set_combo_data(
            self.api_format_combo,
            env_values.get("DOC_TRANS_API_FORMAT", settings.llm.api_format),
        )
        self.base_url_edit.setText(
            env_values.get("DOC_TRANS_BASE_URL", settings.llm.base_url)
        )
        self.api_key_edit.setText(
            env_values.get("DOC_TRANS_API_KEY", settings.llm.api_key)
        )
        self.model_edit.setText(env_values.get("DOC_TRANS_MODEL", settings.llm.model))
        self.anthropic_version_edit.setText(
            env_values.get(
                "DOC_TRANS_ANTHROPIC_VERSION",
                settings.llm.anthropic_version,
            )
        )
        self.timeout_spin.setValue(settings.llm.timeout)
        self.connect_timeout_spin.setValue(settings.llm.connect_timeout)
        self.read_timeout_spin.setValue(settings.llm.read_timeout)
        self.max_retries_spin.setValue(settings.llm.max_retries)
        self.batch_size_spin.setValue(settings.llm.batch_size)
        self.parallel_batches_spin.setValue(settings.llm.parallel_batches)
        self.temperature_spin.setValue(settings.llm.temperature)
        self.max_tokens_edit.setText(
            "" if settings.llm.max_tokens is None else str(settings.llm.max_tokens)
        )

    def _sync_field_state(self) -> None:
        provider = self.provider_combo.currentData()
        api_format = self.api_format_combo.currentData()
        is_mock = provider == "mock"
        uses_anthropic = self._uses_anthropic_compatibility(
            str(provider or ""),
            str(api_format or ""),
        )

        self.base_url_edit.setEnabled(not is_mock)
        self.api_key_edit.setEnabled(not is_mock)
        self.toggle_api_key_visibility_button.setEnabled(not is_mock)
        self.model_edit.setEnabled(True)
        self.anthropic_version_edit.setEnabled(uses_anthropic)

    def _handle_api_key_visibility_toggled(self, checked: bool) -> None:
        self.api_key_edit.setEchoMode(
            QLineEdit.EchoMode.Normal
            if checked
            else QLineEdit.EchoMode.PasswordEchoOnEdit
        )
        self.toggle_api_key_visibility_button.setText("隐藏" if checked else "显示")

    def handle_test_connection_clicked(self) -> None:
        if self._is_connection_test_running():
            return

        try:
            settings = self._build_test_settings()
        except ValueError as exc:
            self._show_connection_test_failure(str(exc))
            return

        self._set_connection_test_running_state(True)
        self._set_connection_test_status("正在测试当前配置的接口连通性...")

        worker = self._build_connection_test_worker(settings)
        worker.succeeded.connect(self._handle_connection_test_succeeded)
        worker.failed.connect(self._handle_connection_test_failed)
        worker.finished.connect(self._handle_connection_test_finished)
        self._connection_worker = worker
        worker.start()

    def accept(self) -> None:
        if self._is_connection_test_running():
            return

        try:
            save_env_file_values(self.project_root, self._build_env_values())
        except ValueError as exc:
            QMessageBox.warning(self, "配置校验失败", str(exc))
            return
        except OSError as exc:
            QMessageBox.warning(self, "保存失败", f"写入 .env 失败：{exc}")
            return

        super().accept()

    def _build_test_settings(self) -> LLMSettings:
        current_settings = load_app_settings(self.project_root).llm
        provider = str(self.provider_combo.currentData() or "").strip()
        api_format = str(self.api_format_combo.currentData() or "").strip()
        base_url = self.base_url_edit.text().strip()
        api_key = self.api_key_edit.text().strip()
        model = self.model_edit.text().strip()
        anthropic_version = self.anthropic_version_edit.text().strip()

        if not provider:
            raise ValueError("Provider 不能为空。")
        if not api_format:
            raise ValueError("API 格式不能为空。")
        if not model:
            raise ValueError("模型名称不能为空。")
        if provider != "mock":
            if not base_url:
                raise ValueError("Base URL 不能为空。")
            if not api_key:
                raise ValueError("API Key 不能为空。")
        if self._uses_anthropic_compatibility(provider, api_format):
            if not anthropic_version:
                raise ValueError("Anthropic Version 不能为空。")

        return LLMSettings(
            provider=provider,
            api_format=api_format,
            anthropic_version=anthropic_version or current_settings.anthropic_version,
            base_url=base_url,
            api_key=api_key,
            model=model,
            timeout=self.timeout_spin.value(),
            connect_timeout=self.connect_timeout_spin.value(),
            read_timeout=self.read_timeout_spin.value(),
            max_retries=self.max_retries_spin.value(),
            batch_size=self.batch_size_spin.value(),
            parallel_batches=self.parallel_batches_spin.value(),
            temperature=self.temperature_spin.value(),
            max_tokens=self._parse_optional_positive_int(
                self.max_tokens_edit.text(),
                field_name="Max Tokens",
            ),
        )

    def _build_connection_test_worker(
        self,
        settings: LLMSettings,
    ) -> ConnectionTestWorker:
        return ConnectionTestWorker(settings=settings, parent=self)

    def _handle_connection_test_succeeded(self, message: str) -> None:
        self._set_connection_test_status(
            f"连接成功：当前配置可用。\n接口响应：{message}",
            color="#027a48",
            tooltip=message,
        )

    def _handle_connection_test_failed(self, message: str) -> None:
        self._show_connection_test_failure(message)

    def _handle_connection_test_finished(self) -> None:
        self._set_connection_test_running_state(False)
        if self._connection_worker is not None:
            self._connection_worker.deleteLater()
            self._connection_worker = None

    def _set_connection_test_running_state(self, running: bool) -> None:
        self.test_connection_button.setEnabled(not running)
        self.save_button.setEnabled(not running)

    def _show_connection_test_failure(self, message: str) -> None:
        summary, suggestion = self._classify_connection_test_failure(message)
        self._set_connection_test_status(
            f"连接失败：{summary}\n建议：{suggestion}\n原始错误：{message}",
            color="#b42318",
            tooltip=message,
        )

    def _classify_connection_test_failure(self, message: str) -> tuple[str, str]:
        upper_message = message.upper()

        if self._contains_any(
            upper_message,
            (
                "HTTP 401",
                "HTTP 403",
                "UNAUTHORIZED",
                "FORBIDDEN",
                "INVALID API KEY",
                "INCORRECT API KEY",
                "AUTHENTICATION",
                "AUTHORIZATION",
            ),
        ):
            return (
                "鉴权失败",
                "请检查 API Key、服务端鉴权方式，以及该模型是否允许当前账号访问。",
            )

        if self._contains_any(
            upper_message,
            (
                "HTTP 404",
                "NOT FOUND",
                "NO ROUTE",
                "/CHAT/COMPLETIONS",
                "/MESSAGES",
            ),
        ):
            return (
                "接口地址可能不正确",
                "请确认 Base URL 是否填写到服务根路径，以及 API 格式是否和服务兼容。",
            )

        if self._contains_any(
            upper_message,
            (
                "HTTP 429",
                "RATE LIMITED",
                "TOO MANY REQUESTS",
                "THROTTL",
            ),
        ):
            return (
                "接口被限流",
                "请稍后重试；如果服务端有限流策略，建议降低并发或避开高峰时段。",
            )

        if self._contains_any(
            upper_message,
            (
                "TIMED OUT",
                "TIMEOUT",
                "READ TIMEOUT",
                "CONNECTTIMEOUT",
                "READTIMEOUT",
            ),
        ):
            return (
                "请求超时",
                "请检查网络质量、服务响应速度，或适当增大 timeout 配置。",
            )

        if self._contains_any(
            upper_message,
            (
                "CERTIFICATE",
                "SSL",
                "TLS",
                "CERT VERIFY FAILED",
            ),
        ):
            return (
                "TLS/证书校验失败",
                "请检查服务端证书链是否完整，以及当前地址是否应使用 HTTPS。",
            )

        if self._contains_any(
            upper_message,
            (
                "NAME OR SERVICE NOT KNOWN",
                "GETADDRINFO",
                "NODENAME",
                "DNS",
                "CONNECTION REFUSED",
                "FAILED TO ESTABLISH A NEW CONNECTION",
                "NO CONNECTION COULD BE MADE",
                "NETWORK IS UNREACHABLE",
            ),
        ):
            return (
                "地址不可达或网络不可用",
                "请检查 Base URL、端口、代理设置，以及本机到服务端的网络连通性。",
            )

        if self._contains_any(
            upper_message,
            (
                "HTTP 500",
                "HTTP 502",
                "HTTP 503",
                "HTTP 504",
                "INTERNAL SERVER ERROR",
                "BAD GATEWAY",
                "SERVICE UNAVAILABLE",
                "GATEWAY TIME-OUT",
            ),
        ):
            return (
                "服务端异常",
                "请确认上游模型服务是否正常，必要时联系接口提供方排查服务端日志。",
            )

        if self._contains_any(
            upper_message,
            (
                "BASE_URL IS REQUIRED",
                "API_KEY IS REQUIRED",
                "MODEL IS REQUIRED",
                "不能为空",
            ),
        ):
            return (
                "配置不完整",
                "请先补齐 Base URL、API Key 和模型名称，再重新测试连接。",
            )

        return (
            "未识别的连接错误",
            "请根据原始错误继续排查；如果是兼容接口问题，优先检查 API 格式和返回结构。",
        )

    def _contains_any(self, haystack: str, needles: tuple[str, ...]) -> bool:
        return any(needle in haystack for needle in needles)

    def _uses_anthropic_compatibility(self, provider: str, api_format: str) -> bool:
        return api_format == "anthropic" or provider == "anthropic_compatible"

    def _is_connection_test_running(self) -> bool:
        return (
            self._connection_worker is not None
            and self._connection_worker.isRunning()
        )

    def _build_env_values(self) -> dict[str, str]:
        max_tokens = self._parse_optional_positive_int(
            self.max_tokens_edit.text(),
            field_name="Max Tokens",
        )
        return {
            "DOC_TRANS_PROVIDER": str(self.provider_combo.currentData() or ""),
            "DOC_TRANS_API_FORMAT": str(self.api_format_combo.currentData() or ""),
            "DOC_TRANS_ANTHROPIC_VERSION": self.anthropic_version_edit.text(),
            "DOC_TRANS_BASE_URL": self.base_url_edit.text(),
            "DOC_TRANS_API_KEY": self.api_key_edit.text(),
            "DOC_TRANS_MODEL": self.model_edit.text(),
            "DOC_TRANS_TIMEOUT": str(self.timeout_spin.value()),
            "DOC_TRANS_CONNECT_TIMEOUT": str(self.connect_timeout_spin.value()),
            "DOC_TRANS_READ_TIMEOUT": str(self.read_timeout_spin.value()),
            "DOC_TRANS_MAX_RETRIES": str(self.max_retries_spin.value()),
            "DOC_TRANS_BATCH_SIZE": str(self.batch_size_spin.value()),
            "DOC_TRANS_PARALLEL_BATCHES": str(self.parallel_batches_spin.value()),
            "DOC_TRANS_TEMPERATURE": self._format_decimal(self.temperature_spin.value()),
            "DOC_TRANS_MAX_TOKENS": "" if max_tokens is None else str(max_tokens),
        }

    def _set_connection_test_status(
        self,
        text: str,
        *,
        color: str = "#666666",
        tooltip: str = "",
    ) -> None:
        self.connection_test_status_label.setText(text)
        self.connection_test_status_label.setToolTip(tooltip)
        self.connection_test_status_label.setStyleSheet(f"color: {color};")

    def _set_combo_data(self, combo_box: QComboBox, value: str) -> None:
        matched_index = combo_box.findData(value)
        combo_box.setCurrentIndex(matched_index if matched_index >= 0 else 0)

    def _parse_optional_positive_int(self, raw_value: str, *, field_name: str) -> int | None:
        value = raw_value.strip()
        if not value:
            return None
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} 必须为整数。") from exc
        if parsed <= 0:
            raise ValueError(f"{field_name} 必须大于 0。")
        return parsed

    def _format_decimal(self, value: float) -> str:
        formatted = f"{value:.2f}".rstrip("0").rstrip(".")
        return formatted or "0"
