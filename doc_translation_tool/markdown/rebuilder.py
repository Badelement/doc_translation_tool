from __future__ import annotations

from doc_translation_tool.markdown.segmenter import SegmentedMarkdownDocument


class MarkdownRebuilder:
    """Restore translated segments into final Markdown text."""

    def rebuild_protected_block_texts(
        self,
        document: SegmentedMarkdownDocument,
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
        document: SegmentedMarkdownDocument,
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
        restored = text
        for placeholder in placeholders:
            restored = restored.replace(placeholder.token, placeholder.raw_text)
        return restored
