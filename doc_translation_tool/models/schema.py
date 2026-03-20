from dataclasses import dataclass


@dataclass(slots=True)
class TranslationTask:
    """Minimal placeholder task model."""

    source_path: str
    output_dir: str
    direction: str
