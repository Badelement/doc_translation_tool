from __future__ import annotations

import json
from pathlib import Path


def load_glossary(path: str | Path) -> list[dict[str, str]]:
    """Load a glossary from a JSON file containing source/target term pairs."""

    glossary_path = Path(path)
    if not glossary_path.exists():
        return []

    with glossary_path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)

    if not isinstance(payload, list):
        raise ValueError("glossary.json must contain a JSON array.")

    glossary: list[dict[str, str]] = []
    for index, item in enumerate(payload, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Glossary item #{index} must be a JSON object.")

        source = item.get("source")
        target = item.get("target")
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"Glossary item #{index} must contain a non-empty string 'source'.")
        if not isinstance(target, str) or not target.strip():
            raise ValueError(f"Glossary item #{index} must contain a non-empty string 'target'.")

        glossary.append(
            {
                "source": source.strip(),
                "target": target.strip(),
            }
        )

    return glossary
