from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_glossary(path: str | Path) -> list[dict[str, str]]:
    """Load a glossary from a JSON file containing source/target term pairs."""

    glossary_path = Path(path)
    if not glossary_path.exists():
        return []

    with glossary_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    return _normalize_glossary_payload(payload)


def save_glossary(path: str | Path, glossary: list[dict[str, str]]) -> Path:
    """Save glossary entries as UTF-8 JSON."""

    glossary_path = Path(path)
    normalized_glossary = _normalize_glossary_payload(glossary)
    glossary_path.parent.mkdir(parents=True, exist_ok=True)
    glossary_path.write_text(
        json.dumps(normalized_glossary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return glossary_path


def _normalize_glossary_payload(payload: Any) -> list[dict[str, str]]:
    if not isinstance(payload, list):
        raise ValueError("glossary.json must contain a JSON array.")

    return [
        _normalize_glossary_item(item, index=index)
        for index, item in enumerate(payload, start=1)
    ]


def _normalize_glossary_item(item: Any, *, index: int) -> dict[str, str]:
    if not isinstance(item, dict):
        raise ValueError(f"Glossary item #{index} must be a JSON object.")

    return {
        "source": _require_non_empty_string(item.get("source"), key="source", index=index),
        "target": _require_non_empty_string(item.get("target"), key="target", index=index),
    }


def _require_non_empty_string(value: Any, *, key: str, index: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(
            f"Glossary item #{index} must contain a non-empty string '{key}'."
        )
    return value.strip()
