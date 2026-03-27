from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re

from dotenv import dotenv_values


EDITABLE_ENV_KEYS = (
    "DOC_TRANS_PROVIDER",
    "DOC_TRANS_API_FORMAT",
    "DOC_TRANS_ANTHROPIC_VERSION",
    "DOC_TRANS_BASE_URL",
    "DOC_TRANS_API_KEY",
    "DOC_TRANS_MODEL",
    "DOC_TRANS_TIMEOUT",
    "DOC_TRANS_CONNECT_TIMEOUT",
    "DOC_TRANS_READ_TIMEOUT",
    "DOC_TRANS_MAX_RETRIES",
    "DOC_TRANS_BATCH_SIZE",
    "DOC_TRANS_PARALLEL_BATCHES",
    "DOC_TRANS_TEMPERATURE",
    "DOC_TRANS_MAX_TOKENS",
)

_ASSIGNMENT_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")
_NEEDS_QUOTES_RE = re.compile(r'[\s#"\']')


def load_env_file_values(project_root: str | Path) -> dict[str, str]:
    env_path = Path(project_root) / ".env"
    if not env_path.exists():
        return {}

    values = dotenv_values(env_path)
    return {
        key: value
        for key, value in values.items()
        if isinstance(key, str) and value is not None
    }


def save_env_file_values(
    project_root: str | Path,
    values: Mapping[str, str],
) -> Path:
    env_path = Path(project_root) / ".env"
    sanitized_values = {
        key: str(value).strip()
        for key, value in values.items()
        if key in EDITABLE_ENV_KEYS
    }

    existing_lines: list[str] = []
    if env_path.exists():
        existing_lines = env_path.read_text(encoding="utf-8").splitlines()

    written_keys: set[str] = set()
    updated_lines: list[str] = []
    for line in existing_lines:
        matched_key = _extract_assignment_key(line)
        if matched_key is None or matched_key not in sanitized_values:
            updated_lines.append(line)
            continue

        updated_lines.append(
            f"{matched_key}={_serialize_env_value(sanitized_values[matched_key])}"
        )
        written_keys.add(matched_key)

    missing_keys = [
        key
        for key in EDITABLE_ENV_KEYS
        if key in sanitized_values and key not in written_keys
    ]
    if missing_keys and updated_lines and updated_lines[-1] != "":
        updated_lines.append("")

    for key in missing_keys:
        updated_lines.append(f"{key}={_serialize_env_value(sanitized_values[key])}")

    env_path.write_text("\n".join(updated_lines).rstrip() + "\n", encoding="utf-8")
    return env_path


def _extract_assignment_key(line: str) -> str | None:
    match = _ASSIGNMENT_RE.match(line)
    if match is None:
        return None
    return match.group(1)


def _serialize_env_value(value: str) -> str:
    if value == "":
        return ""
    if _NEEDS_QUOTES_RE.search(value) is None:
        return value
    escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped_value}"'
