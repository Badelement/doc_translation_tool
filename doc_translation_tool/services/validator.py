from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass(slots=True)
class InputValidationResult:
    """Validation result for the translation form inputs."""

    valid: bool
    source_path: str = ""
    output_dir: str = ""
    errors: list[str] = field(default_factory=list)
    auto_filled_output_dir: bool = False


def validate_translation_inputs(
    source_text: str,
    output_text: str,
) -> InputValidationResult:
    source_path = Path(source_text).expanduser() if source_text.strip() else None
    output_path = Path(output_text).expanduser() if output_text.strip() else None

    errors: list[str] = []
    normalized_source = ""
    normalized_output = ""
    auto_filled_output_dir = False

    if source_path is None:
        errors.append("目标翻译文件不能为空")
    else:
        normalized_source = str(source_path)
        if not source_path.exists():
            errors.append("目标翻译文件不存在")
        elif not source_path.is_file():
            errors.append("目标翻译文件必须为文件")
        elif source_path.suffix.lower() != ".md":
            errors.append("目标翻译文件必须为 .md 格式")

    if output_path is None and source_path is not None and source_path.is_file():
        output_path = source_path.parent
        normalized_output = str(output_path)
        auto_filled_output_dir = True
    elif output_path is not None:
        normalized_output = str(output_path)

    if output_path is None:
        errors.append("生成目录不能为空")
    else:
        if not output_path.exists():
            errors.append("生成目录不存在")
        elif not output_path.is_dir():
            errors.append("生成目录必须为文件夹路径")

    return InputValidationResult(
        valid=not errors,
        source_path=normalized_source,
        output_dir=normalized_output,
        errors=errors,
        auto_filled_output_dir=auto_filled_output_dir,
    )
