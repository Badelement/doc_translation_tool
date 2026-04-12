from __future__ import annotations

from doc_translation_tool.documents.base import PreparedDocument


class MarkdownRebuilder:
    """Restore translated segments into final Markdown text."""

    def rebuild_protected_block_texts(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str] | None = None,
    ) -> list[str]:
        segment_map = {
            segment.id: segment.text
            for segment in document.segments
        }
        if translated_segment_texts:
            segment_map.update(translated_segment_texts)

        rebuilt_blocks: list[str] = []
        for block in document.blocks:
            if not block.segment_ids:
                rebuilt_blocks.append(block.protected_text)
                continue

            rebuilt_blocks.append(
                "".join(segment_map[segment_id] for segment_id in block.segment_ids)
            )

        return rebuilt_blocks

    def rebuild_document(
        self,
        document: PreparedDocument,
        translated_segment_texts: dict[str, str] | None = None,
    ) -> str:
        restored_blocks: list[str] = []
        rebuilt_blocks = self.rebuild_protected_block_texts(
            document,
            translated_segment_texts,
        )

        for block, rebuilt_text in zip(document.blocks, rebuilt_blocks, strict=True):
            restored_blocks.append(self._restore_text(rebuilt_text, block.placeholders))

        restored = "\n".join(restored_blocks)
        if document.trailing_newline:
            restored += "\n"
        return restored

    def _restore_text(self, text: str, placeholders) -> str:
        if not placeholders:
            return text

        # Sort placeholders by token length (longest first) to avoid partial replacements
        sorted_placeholders = sorted(placeholders, key=lambda p: len(p.token), reverse=True)

        # Build replacement map
        replacements = {p.token: p.raw_text for p in sorted_placeholders}

        # Single-pass replacement using str.replace
        restored = text
        for token, raw_text in replacements.items():
            restored = restored.replace(token, raw_text)
        return restored
