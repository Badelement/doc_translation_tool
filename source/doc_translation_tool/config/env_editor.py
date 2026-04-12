from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
import re
import sys

if sys.platform == "win32":
    import ctypes

from dotenv import dotenv_values


EDITABLE_ENV_KEYS = (
    "DOC_TRANS_PROVIDER",
    "DOC_TRANS_API_FORMAT",
    "DOC_TRANS_ANTHROPIC_VERSION",
    "DOC_TRANS_BASE_URL",
    "DOC_TRANS_API_KEY",
    "DOC_TRANS_MODEL",
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

    existing_lines = []
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
        key for key in EDITABLE_ENV_KEYS if key in sanitized_values and key not in written_keys
    ]
    if missing_keys and updated_lines and updated_lines[-1] != "":
        updated_lines.append("")

    for key in missing_keys:
        updated_lines.append(f"{key}={_serialize_env_value(sanitized_values[key])}")

    _prepare_env_path_for_write(env_path)
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


def _prepare_env_path_for_write(env_path: Path) -> None:
    if not env_path.exists():
        return
    if sys.platform != "win32":
        return

    _clear_windows_file_attributes(env_path)


def _clear_windows_file_attributes(env_path: Path) -> None:
    windows_path = str(env_path)
    file_attributes = ctypes.windll.kernel32.GetFileAttributesW(windows_path)
    if file_attributes == 0xFFFFFFFF:
        return

    protected_flags = 0x01 | 0x02 | 0x04  # readonly, hidden, system
    updated_attributes = file_attributes & ~protected_flags
    if updated_attributes == file_attributes:
        return
    if updated_attributes == 0:
        updated_attributes = 0x80  # FILE_ATTRIBUTE_NORMAL

    if not ctypes.windll.kernel32.SetFileAttributesW(
        windows_path,
        updated_attributes,
    ):
        raise OSError(f"Failed to update file attributes for {env_path}")
