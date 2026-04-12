from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from dotenv import dotenv_values


@dataclass(slots=True)
class LLMSettings:
    """Configuration for the LLM integration layer."""

    provider: str = "openai_compatible"
    api_format: str = "openai"
    anthropic_version: str = "2023-06-01"
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    timeout: int = 60
    connect_timeout: int = 10
    read_timeout: int = 60
    max_retries: int = 2
    batch_size: int = 8
    parallel_batches: int = 2
    temperature: float = 0.2
    max_tokens: int | None = None
    validation_mode: str = "balanced"
    residual_language_threshold: int = 5
    allow_placeholder_reorder: bool = False
    min_batch_split_size: int = 2

    @property
    def api_key_configured(self) -> bool:
        return bool(self.api_key.strip())


@dataclass(slots=True)
class AppSettings:
    """Application settings loaded from files and environment."""

    app_name: str = "Document Translation Tool"
    project_root: str = ""
    llm: LLMSettings = field(default_factory=LLMSettings)
    front_matter_translatable_fields: tuple[str, ...] = ("title", "subtitle", "desc")


def load_app_settings(
    project_root: str | Path | None = None,
    env_overrides: dict[str, str] | None = None,
) -> AppSettings:
    root = Path(project_root) if project_root is not None else Path.cwd()
    settings_payload = _load_settings_json(root / "settings.json")
    llm_payload = settings_payload.get("llm", {})
    markdown_payload = settings_payload.get("markdown", {})

    dotenv_payload = _normalize_mapping(dotenv_values(root / ".env"))
    env_payload = _extract_env_values(env_overrides or os.environ)

    merged_llm = _merge_llm_sources(
        llm_payload=llm_payload,
        dotenv_payload=dotenv_payload,
        env_payload=env_payload,
    )
    front_matter_fields = _resolve_front_matter_fields(
        markdown_payload=markdown_payload,
        dotenv_payload=dotenv_payload,
        env_payload=env_payload,
    )

    return AppSettings(
        project_root=str(root),
        llm=LLMSettings(
            provider=str(merged_llm.get("provider", "openai_compatible")),
            api_format=str(merged_llm.get("api_format", "openai")),
            anthropic_version=str(merged_llm.get("anthropic_version", "2023-06-01")),
            base_url=str(merged_llm.get("base_url", "")),
            api_key=str(merged_llm.get("api_key", "")),
            model=str(merged_llm.get("model", "")),
            timeout=_to_int(merged_llm.get("timeout"), 60, min_val=1, max_val=600),
            connect_timeout=_to_int(merged_llm.get("connect_timeout"), 10, min_val=1, max_val=60),
            read_timeout=_to_int(merged_llm.get("read_timeout"), 60, min_val=1, max_val=600),
            max_retries=_to_int(merged_llm.get("max_retries"), 2, min_val=0, max_val=10),
            batch_size=_to_int(merged_llm.get("batch_size"), 8, min_val=1, max_val=100),
            parallel_batches=_to_int(merged_llm.get("parallel_batches"), 2, min_val=1, max_val=20),
            temperature=_to_float(merged_llm.get("temperature"), 0.2, min_val=0.0, max_val=2.0),
            max_tokens=_to_optional_int(merged_llm.get("max_tokens"), min_val=1, max_val=1000000),
            validation_mode=str(merged_llm.get("validation_mode", "balanced")),
            residual_language_threshold=_to_int(merged_llm.get("residual_language_threshold"), 5, min_val=1, max_val=50),
            allow_placeholder_reorder=_to_bool(merged_llm.get("allow_placeholder_reorder"), False),
            min_batch_split_size=_to_int(merged_llm.get("min_batch_split_size"), 2, min_val=1, max_val=10),
        ),
        front_matter_translatable_fields=front_matter_fields,
    )


def summarize_settings(settings: AppSettings) -> str:
    """Return a safe, user-facing summary without exposing the API key."""

    api_key_status = "configured" if settings.llm.api_key_configured else "missing"
    return "\n".join(
        [
            f"App: {settings.app_name}",
            f"Project root: {settings.project_root}",
            f"Provider: {settings.llm.provider}",
            f"API format: {settings.llm.api_format}",
            f"Anthropic version: {settings.llm.anthropic_version}",
            f"Base URL: {settings.llm.base_url or '<empty>'}",
            f"Model: {settings.llm.model or '<empty>'}",
            f"API key: {api_key_status}",
            "Front matter fields: "
            + ", ".join(settings.front_matter_translatable_fields),
        ]
    )


def _load_settings_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as file:
        payload = json.load(file)

    if not isinstance(payload, dict):
        raise ValueError("settings.json must contain a JSON object at the top level.")
    return payload


def _normalize_mapping(raw_mapping: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in raw_mapping.items():
        if value is None:
            continue
        normalized[key] = value
    return normalized


def _extract_env_values(raw_env: dict[str, str]) -> dict[str, str]:
    key_mapping = {
        "DOC_TRANS_PROVIDER": "provider",
        "DOC_TRANS_API_FORMAT": "api_format",
        "DOC_TRANS_ANTHROPIC_VERSION": "anthropic_version",
        "DOC_TRANS_BASE_URL": "base_url",
        "DOC_TRANS_API_KEY": "api_key",
        "DOC_TRANS_MODEL": "model",
        "DOC_TRANS_TIMEOUT": "timeout",
        "DOC_TRANS_CONNECT_TIMEOUT": "connect_timeout",
        "DOC_TRANS_READ_TIMEOUT": "read_timeout",
        "DOC_TRANS_MAX_RETRIES": "max_retries",
        "DOC_TRANS_BATCH_SIZE": "batch_size",
        "DOC_TRANS_PARALLEL_BATCHES": "parallel_batches",
        "DOC_TRANS_TEMPERATURE": "temperature",
        "DOC_TRANS_MAX_TOKENS": "max_tokens",
        "DOC_TRANS_VALIDATION_MODE": "validation_mode",
        "DOC_TRANS_RESIDUAL_LANGUAGE_THRESHOLD": "residual_language_threshold",
        "DOC_TRANS_ALLOW_PLACEHOLDER_REORDER": "allow_placeholder_reorder",
        "DOC_TRANS_MIN_BATCH_SPLIT_SIZE": "min_batch_split_size",
        "DOC_TRANS_FRONT_MATTER_FIELDS": "front_matter_fields",
    }

    result: dict[str, str] = {}
    for env_key, config_key in key_mapping.items():
        value = raw_env.get(env_key)
        if value is None or value == "":
            continue
        result[config_key] = value

    return result


def _merge_llm_sources(
    *,
    llm_payload: dict[str, Any],
    dotenv_payload: dict[str, Any],
    env_payload: dict[str, Any],
) -> dict[str, Any]:
    merged = dict(llm_payload)
    merged.update(_extract_env_values(dotenv_payload))
    merged.update(env_payload)
    return merged


def _resolve_front_matter_fields(
    *,
    markdown_payload: dict[str, Any],
    dotenv_payload: dict[str, Any],
    env_payload: dict[str, Any],
) -> tuple[str, ...]:
    raw_value = markdown_payload.get(
        "front_matter_translatable_fields",
        ("title", "subtitle", "desc"),
    )

    dotenv_value = _extract_env_values(dotenv_payload).get("front_matter_fields")
    if dotenv_value not in (None, ""):
        raw_value = dotenv_value

    env_value = env_payload.get("front_matter_fields")
    if env_value not in (None, ""):
        raw_value = env_value

    return _parse_front_matter_fields(raw_value)


def _to_int(value: Any, default: int, min_val: int | None = None, max_val: int | None = None) -> int:
    if value in (None, ""):
        return default
    try:
        result = int(value)
        if min_val is not None and result < min_val:
            return default
        if max_val is not None and result > max_val:
            return default
        return result
    except (ValueError, TypeError):
        return default


def _to_float(value: Any, default: float, min_val: float | None = None, max_val: float | None = None) -> float:
    if value in (None, ""):
        return default
    try:
        result = float(value)
        if min_val is not None and result < min_val:
            return default
        if max_val is not None and result > max_val:
            return default
        return result
    except (ValueError, TypeError):
        return default


def _to_optional_int(value: Any, min_val: int | None = None, max_val: int | None = None) -> int | None:
    if value in (None, ""):
        return None
    try:
        result = int(value)
        if min_val is not None and result < min_val:
            return None
        if max_val is not None and result > max_val:
            return None
        return result
    except (ValueError, TypeError):
        return None


def _to_bool(value: Any, default: bool) -> bool:
    if value in (None, ""):
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.lower() in ("true", "1", "yes", "on")
    return bool(value)


def _parse_front_matter_fields(value: Any) -> tuple[str, ...]:
    if isinstance(value, str):
        items = [item.strip().lower() for item in value.split(",")]
    elif isinstance(value, (list, tuple)):
        items = [str(item).strip().lower() for item in value]
    else:
        raise ValueError("front_matter_translatable_fields must be a string or array.")

    normalized = tuple(item for item in items if item)
    if not normalized:
        raise ValueError("front_matter_translatable_fields must not be empty.")
    return normalized
