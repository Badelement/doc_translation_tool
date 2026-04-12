from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from doc_translation_tool.document_types import (
    is_supported_document,
    supported_source_error_message,
)


@dataclass(slots=True)
class InputValidationResult:
    """Validation result for the translation form inputs."""

    valid: bool
    source_path: str = ""
    source_paths: list[str] = field(default_factory=list)
    output_dir: str = ""
    errors: list[str] = field(default_factory=list)
    auto_filled_output_dir: bool = False


def validate_translation_inputs(
    source_text: str,
    output_text: str,
    *,
    source_mode: str = "file",
) -> InputValidationResult:
    source_path = _normalize_optional_path(source_text)
    output_path = _normalize_optional_path(output_text)

    errors: list[str] = []
    normalized_source = _validate_source_path(
        source_path,
        errors,
        source_mode=source_mode,
    )
    output_path, auto_filled_output_dir = _resolve_output_path(output_path, source_path)
    normalized_output = _validate_output_path(output_path, errors)

    return InputValidationResult(
        valid=not errors,
        source_path=normalized_source,
        output_dir=normalized_output,
        errors=errors,
        auto_filled_output_dir=auto_filled_output_dir,
    )


def validate_batch_translation_inputs(
    source_text: str,
    output_text: str,
) -> InputValidationResult:
    return validate_translation_inputs(
        source_text,
        output_text,
        source_mode="directory",
    )


def validate_multi_file_translation_inputs(
    source_paths: list[str],
    output_text: str,
) -> InputValidationResult:
    normalized_paths: list[str] = []
    seen_paths: set[str] = set()
    errors: list[str] = []

    for raw_path in source_paths:
        candidate = _normalize_optional_path(raw_path)
        if candidate is None:
            continue

        normalized_path = str(candidate)
        if normalized_path in seen_paths:
            continue
        seen_paths.add(normalized_path)

        if not candidate.exists():
            errors.append(f"多文件任务源文件不存在：{normalized_path}")
            continue
        if not candidate.is_file():
            errors.append(f"多文件任务源路径必须为文件：{normalized_path}")
            continue
        if not is_supported_document(candidate):
            errors.append(f"多文件任务仅支持 .md 或 .dita 文件：{normalized_path}")
            continue

        normalized_paths.append(normalized_path)

    if not normalized_paths:
        errors.append("多文件任务源文件不能为空")

    output_path = _normalize_optional_path(output_text)
    normalized_output = _validate_output_path(output_path, errors)

    return InputValidationResult(
        valid=not errors,
        source_paths=normalized_paths,
        output_dir=normalized_output,
        errors=errors,
    )


def _normalize_optional_path(path_text: str) -> Path | None:
    stripped = path_text.strip()
    if not stripped:
        return None
    return Path(stripped).expanduser()


def _validate_source_path(
    source_path: Path | None,
    errors: list[str],
    *,
    source_mode: str,
) -> str:
    if source_path is None:
        if source_mode == "directory":
            errors.append("批量翻译源目录不能为空")
        else:
            errors.append("目标翻译文件不能为空")
        return ""

    normalized_source = str(source_path)
    if source_mode == "directory":
        if not source_path.exists():
            errors.append("批量翻译源目录不存在")
        elif not source_path.is_dir():
            errors.append("批量翻译源路径必须为文件夹路径")
        return normalized_source

    if source_mode != "file":
        raise ValueError(f"Unsupported source_mode: {source_mode}")

    if not source_path.exists():
        errors.append("目标翻译文件不存在")
    elif not source_path.is_file():
        errors.append("目标翻译文件必须为文件")
    elif not is_supported_document(source_path):
        errors.append(supported_source_error_message())

    return normalized_source


def _resolve_output_path(
    output_path: Path | None,
    source_path: Path | None,
) -> tuple[Path | None, bool]:
    if output_path is not None:
        return output_path, False

    if source_path is not None and source_path.is_file():
        return source_path.parent, True

    return None, False


def _validate_output_path(output_path: Path | None, errors: list[str]) -> str:
    if output_path is None:
        errors.append("生成目录不能为空")
        return ""

    normalized_output = str(output_path)
    if not output_path.exists():
        errors.append("生成目录不存在")
    elif not output_path.is_dir():
        errors.append("生成目录必须为文件夹路径")

    return normalized_output
