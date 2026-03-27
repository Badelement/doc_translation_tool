from __future__ import annotations

import os
import tempfile
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


class DocumentOutputWriter:
    """Write translated document text to a UTF-8 encoded output file."""

    def build_output_filename(
        self,
        source_path: str | Path,
        direction: str,
        *,
        output_extension: str | None = None,
    ) -> str:
        source = Path(source_path)
        suffix = self._direction_suffix(direction)
        extension = output_extension or source.suffix
        return f"{source.stem}_{suffix}{extension}"

    def build_output_path(
        self,
        source_path: str | Path,
        output_dir: str | Path,
        direction: str,
        *,
        output_extension: str | None = None,
    ) -> Path:
        output_directory = Path(output_dir)
        return output_directory / self.build_output_filename(
            source_path,
            direction,
            output_extension=output_extension,
        )

    def write_output(
        self,
        *,
        source_path: str | Path,
        output_dir: str | Path,
        direction: str,
        document_text: str,
        output_extension: str | None = None,
    ) -> OutputWriteResult:
        source, output_directory = self._normalize_paths(
            source_path=source_path,
            output_dir=output_dir,
        )
        output_path = self.build_output_path(
            source,
            output_directory,
            direction,
            output_extension=output_extension,
        )
        self._validate_output_directory(output_directory)
        self._validate_output_path(source=source, output_path=output_path)
        self._write_text_atomically(output_path, document_text)

        return OutputWriteResult(
            output_path=str(output_path),
            file_name=output_path.name,
            bytes_written=len(document_text.encode("utf-8")),
        )

    def _direction_suffix(self, direction: str) -> str:
        if direction == "zh_to_en":
            return "en"
        if direction == "en_to_zh":
            return "zh"
        raise OutputWriteError(f"Unsupported translation direction: {direction}")

    def _normalize_paths(
        self,
        *,
        source_path: str | Path,
        output_dir: str | Path,
    ) -> tuple[Path, Path]:
        return Path(source_path).expanduser(), Path(output_dir).expanduser()

    def _validate_output_directory(self, output_directory: Path) -> None:
        if not output_directory.exists():
            raise OutputWriteError("Output directory does not exist.")
        if not output_directory.is_dir():
            raise OutputWriteError("Output directory must be a directory path.")

    def _validate_output_path(self, *, source: Path, output_path: Path) -> None:
        source_resolved = source.resolve(strict=False)
        output_resolved = output_path.resolve(strict=False)
        if source_resolved == output_resolved:
            raise OutputWriteError("Output path must not overwrite the source file.")

    def _write_text_atomically(self, output_path: Path, document_text: str) -> None:
        file_descriptor, temp_path_str = tempfile.mkstemp(
            dir=output_path.parent,
            prefix=f".{output_path.name}.",
            suffix=".tmp",
        )
        temp_path = Path(temp_path_str)
        try:
            with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="") as handle:
                handle.write(document_text)
            temp_path.replace(output_path)
        except Exception:
            temp_path.unlink(missing_ok=True)
            raise


class MarkdownOutputWriter(DocumentOutputWriter):
    """Backward-compatible Markdown-specialized output writer."""

    def build_output_filename(
        self,
        source_path: str | Path,
        direction: str,
        *,
        output_extension: str | None = None,
    ) -> str:
        return super().build_output_filename(
            source_path,
            direction,
            output_extension=".md",
        )

    def write_output(
        self,
        *,
        source_path: str | Path,
        output_dir: str | Path,
        direction: str,
        markdown_text: str,
    ) -> OutputWriteResult:
        source = Path(source_path).expanduser()
        if source.suffix.lower() != ".md":
            raise OutputWriteError("Source file must be a Markdown file.")

        return super().write_output(
            source_path=source,
            output_dir=output_dir,
            direction=direction,
            document_text=markdown_text,
            output_extension=".md",
        )
