from dataclasses import dataclass


@dataclass(slots=True)
class TranslationTask:
    """Minimal placeholder task model."""

    source_path: str
    output_dir: str
    direction: str


@dataclass(slots=True)
class MultiFileTranslationTask:
    """Task model for an explicit list of source files."""

    source_paths: list[str]
    output_dir: str
    direction: str


@dataclass(slots=True)
class BatchTranslationTask:
    """Task model for directory-based batch translation."""

    source_dir: str
    output_dir: str
    direction: str
    recursive: bool = False
