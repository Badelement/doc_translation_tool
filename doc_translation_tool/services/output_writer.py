from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class OutputWriteResult:
    """Metadata for a successfully written translation output file."""

    output_path: str
    file_name: str
    bytes_written: int


class OutputWriteError(RuntimeError):
    """Raised when the translated Markdown output cannot be written safely."""


class MarkdownOutputWriter:
    """Write translated Markdown text to a new UTF-8 encoded output file."""

    def build_output_filename(self, source_path: str | Path, direction: str) -> str:
        source = Path(source_path)
        suffix = self._direction_suffix(direction)
        return f"{source.stem}_{suffix}.md"

    def build_output_path(
        self,
        source_path: str | Path,
        output_dir: str | Path,
        direction: str,
    ) -> Path:
        output_directory = Path(output_dir)
        return output_directory / self.build_output_filename(source_path, direction)

    def write_output(
        self,
        *,
        source_path: str | Path,
        output_dir: str | Path,
        direction: str,
        markdown_text: str,
    ) -> OutputWriteResult:
        source = Path(source_path).expanduser()
        output_directory = Path(output_dir).expanduser()
        output_path = self.build_output_path(source, output_directory, direction)

        if source.suffix.lower() != ".md":
            raise OutputWriteError("Source file must be a Markdown file.")
        if not output_directory.exists():
            raise OutputWriteError("Output directory does not exist.")
        if not output_directory.is_dir():
            raise OutputWriteError("Output directory must be a directory path.")
        if output_path.exists():
            raise OutputWriteError(f"Output file already exists: {output_path}")

        source_resolved = source.resolve(strict=False)
        output_resolved = output_path.resolve(strict=False)
        if source_resolved == output_resolved:
            raise OutputWriteError("Output path must not overwrite the source file.")

        with output_path.open("w", encoding="utf-8", newline="") as handle:
            handle.write(markdown_text)

        return OutputWriteResult(
            output_path=str(output_path),
            file_name=output_path.name,
            bytes_written=len(markdown_text.encode("utf-8")),
        )

    def _direction_suffix(self, direction: str) -> str:
        if direction == "zh_to_en":
            return "en"
        if direction == "en_to_zh":
            return "zh"
        raise OutputWriteError(f"Unsupported translation direction: {direction}")
