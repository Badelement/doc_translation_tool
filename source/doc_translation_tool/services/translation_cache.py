from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

from doc_translation_tool.documents.base import PreparedDocument


@dataclass(slots=True)
class TranslationCheckpoint:
    source_path: str
    direction: str
    document_fingerprint: str
    translated_segment_texts: dict[str, str]


class TranslationCheckpointError(RuntimeError):
    """Raised when a persisted checkpoint cache cannot be read safely."""


class TranslationCheckpointCache:
    """Persist partial segment translations for safe resume after failures."""

    def build_cache_path(
        self,
        *,
        source_path: str | Path,
        output_dir: str | Path,
        direction: str,
    ) -> Path:
        source = Path(source_path)
        safe_stem = source.stem or "document"
        source_hash = hashlib.sha256(str(source.resolve(strict=False)).encode("utf-8")).hexdigest()[:12]
        cache_dir = Path(output_dir) / ".doc_translation_cache"
        return cache_dir / f"{safe_stem}_{direction}_{source_hash}.json"

    def build_document_fingerprint(
        self,
        document: PreparedDocument,
    ) -> str:
        payload = self._build_fingerprint_payload(document)
        serialized = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        return hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    def load(
        self,
        path: str | Path,
        *,
        source_path: str | Path,
        direction: str,
        document_fingerprint: str,
    ) -> dict[str, str]:
        cache_path = Path(path)
        if not cache_path.exists():
            return {}

        payload = self._load_payload(cache_path)
        if payload is None:
            return {}

        if not self._matches_checkpoint_metadata(
            payload,
            source_path=source_path,
            direction=direction,
            document_fingerprint=document_fingerprint,
        ):
            return {}

        return self._normalize_translated_segment_texts(
            payload.get("translated_segment_texts")
        )

    def save(
        self,
        path: str | Path,
        checkpoint: TranslationCheckpoint,
    ) -> None:
        cache_path = Path(path)
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        payload = self._build_checkpoint_payload(checkpoint)
        with temp_path.open("w", encoding="utf-8", newline="") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2, sort_keys=True)
        temp_path.replace(cache_path)

    def clear(self, path: str | Path) -> None:
        cache_path = Path(path)
        if cache_path.exists():
            cache_path.unlink()
        temp_path = cache_path.with_suffix(cache_path.suffix + ".tmp")
        if temp_path.exists():
            temp_path.unlink()
        cache_dir = cache_path.parent
        if cache_dir.exists() and cache_dir.is_dir():
            try:
                cache_dir.rmdir()
            except OSError:
                pass

    def _build_fingerprint_payload(
        self,
        document: PreparedDocument,
    ) -> dict[str, object]:
        return {
            "document_type": document.document_type,
            "trailing_newline": document.trailing_newline,
            "segments": [
                {
                    "id": segment.id,
                    "block_index": segment.block_index,
                    "block_type": segment.block_type,
                    "order_in_block": segment.order_in_block,
                    "text": segment.text,
                }
                for segment in document.segments
            ],
        }

    def _load_payload(self, cache_path: Path) -> dict[str, object] | None:
        try:
            with cache_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (OSError, json.JSONDecodeError) as exc:
            raise TranslationCheckpointError(
                f"Failed to read checkpoint cache {cache_path}: {exc}"
            ) from exc

        if not isinstance(payload, dict):
            raise TranslationCheckpointError(
                f"Checkpoint cache {cache_path} must contain a JSON object."
            )
        return payload

    def _matches_checkpoint_metadata(
        self,
        payload: dict[str, object],
        *,
        source_path: str | Path,
        direction: str,
        document_fingerprint: str,
    ) -> bool:
        return (
            payload.get("source_path") == str(source_path)
            and payload.get("direction") == direction
            and payload.get("document_fingerprint") == document_fingerprint
        )

    def _normalize_translated_segment_texts(
        self,
        translated_segment_texts: object,
    ) -> dict[str, str]:
        if not isinstance(translated_segment_texts, dict):
            return {}

        return {
            str(segment_id): translated_text
            for segment_id, translated_text in translated_segment_texts.items()
            if isinstance(segment_id, str) and isinstance(translated_text, str)
        }

    def _build_checkpoint_payload(
        self,
        checkpoint: TranslationCheckpoint,
    ) -> dict[str, object]:
        return {
            "source_path": checkpoint.source_path,
            "direction": checkpoint.direction,
            "document_fingerprint": checkpoint.document_fingerprint,
            "translated_segment_texts": checkpoint.translated_segment_texts,
        }
