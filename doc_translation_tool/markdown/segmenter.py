from __future__ import annotations

from dataclasses import dataclass, field
import re

from doc_translation_tool.documents.base import (
    DocumentSegment,
    PreparedDocument,
    PreparedDocumentBlock,
)
from doc_translation_tool.markdown.protector import (
    ProtectedMarkdownBlock,
    ProtectedMarkdownDocument,
    ProtectedPlaceholder,
)


@dataclass(slots=True)
class TranslationSegment(DocumentSegment):
    """Single translatable segment generated from a protected Markdown block."""


@dataclass(slots=True)
class SegmentedMarkdownBlock(PreparedDocumentBlock):
    """Protected block plus the translation segment IDs derived from it."""

    placeholders: list[ProtectedPlaceholder] = field(default_factory=list)


@dataclass(slots=True)
class SegmentedMarkdownDocument(PreparedDocument):
    """Segmented representation ready for batch translation."""

    blocks: list[SegmentedMarkdownBlock]
    segments: list[TranslationSegment]
    document_type: str = "markdown"


class MarkdownSegmenter:
    """Split protected Markdown text into stable, model-friendly segments."""

    _HTML_BREAK_RE = re.compile(r"(<br\s*/?>)", flags=re.IGNORECASE)

    def __init__(self, *, max_segment_length: int = 500) -> None:
        if max_segment_length <= 0:
            raise ValueError("max_segment_length must be greater than zero.")
        self.max_segment_length = max_segment_length
        self._segment_counter = 0

    def segment(self, document: ProtectedMarkdownDocument) -> SegmentedMarkdownDocument:
        blocks: list[SegmentedMarkdownBlock] = []
        segments: list[TranslationSegment] = []

        for block_index, block in enumerate(document.blocks):
            chunk_texts = self._split_block_text(block)
            segment_ids: list[str] = []

            for order_in_block, chunk_text in enumerate(chunk_texts):
                segment = TranslationSegment(
                    id=self._next_segment_id(),
                    block_index=block_index,
                    block_type=block.block_type,
                    order_in_block=order_in_block,
                    text=chunk_text,
                )
                segments.append(segment)
                segment_ids.append(segment.id)

            blocks.append(
                SegmentedMarkdownBlock(
                    block_index=block_index,
                    block_type=block.block_type,
                    protected_text=block.protected_text,
                    placeholders=list(block.placeholders),
                    segment_ids=segment_ids,
                    translatable=block.translatable,
                    meta=dict(block.meta),
                )
            )

        return SegmentedMarkdownDocument(
            blocks=blocks,
            segments=segments,
            trailing_newline=document.trailing_newline,
            document_type="markdown",
        )

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

            rebuilt_text = "".join(segment_map[segment_id] for segment_id in block.segment_ids)
            rebuilt_blocks.append(rebuilt_text)

        return rebuilt_blocks

    def _split_block_text(self, block: ProtectedMarkdownBlock) -> list[str]:
        if not block.translatable:
            return []
        if block.block_type == "blank_line":
            return []
        if block.block_type == "table":
            return self._pack_table_lines(block.protected_text)
        if len(block.protected_text) <= self.max_segment_length:
            return [block.protected_text] if block.protected_text else []

        sentence_chunks = self._split_by_sentence(block.protected_text)
        sentence_segments = self._pack_chunks(sentence_chunks)
        if self._all_within_limit(sentence_segments):
            return sentence_segments

        newline_chunks = self._split_by_newline(block.protected_text)
        newline_segments = self._pack_chunks(newline_chunks)
        if self._all_within_limit(newline_segments):
            return newline_segments

        return self._hard_split(block.protected_text)

    def _split_by_sentence(self, text: str) -> list[str]:
        chunks: list[str] = []
        current: list[str] = []

        for index, char in enumerate(text):
            current.append(char)
            if self._is_sentence_boundary(text, index):
                chunk = "".join(current)
                if chunk:
                    chunks.append(chunk)
                current = []

        if current:
            chunks.append("".join(current))

        return [chunk for chunk in chunks if chunk]

    def _split_by_newline(self, text: str) -> list[str]:
        return [line for line in text.splitlines(keepends=True) if line]

    def _pack_table_lines(self, text: str) -> list[str]:
        lines = self._split_by_newline(text)
        if not lines:
            return []

        expanded_lines: list[str] = []
        for line in lines:
            expanded_lines.extend(self._split_table_line(line))

        packed: list[str] = []
        current = ""

        for line in expanded_lines:
            if not current:
                current = line
                continue

            if len(current) + len(line) <= self.max_segment_length:
                current += line
            else:
                packed.append(current)
                current = line

        if current:
            packed.append(current)

        return packed

    def _split_table_line(self, line: str) -> list[str]:
        if len(line) <= self.max_segment_length:
            return [line]

        if self._HTML_BREAK_RE.search(line) is None:
            return [line]

        html_break_chunks = self._split_by_html_break(line)
        html_break_segments = self._pack_chunks(html_break_chunks)
        if len(html_break_segments) > 1 and self._all_within_limit(html_break_segments):
            return html_break_segments

        whitespace_chunks = self._split_by_whitespace(line)
        whitespace_segments = self._pack_chunks(whitespace_chunks)
        if self._all_within_limit(whitespace_segments):
            return whitespace_segments

        return self._hard_split(line)

    def _pack_chunks(self, chunks: list[str]) -> list[str]:
        if not chunks:
            return []

        packed: list[str] = []
        current = ""

        for chunk in chunks:
            if len(chunk) > self.max_segment_length:
                if current:
                    packed.append(current)
                    current = ""
                packed.extend(self._hard_split(chunk))
                continue

            if not current:
                current = chunk
                continue

            if len(current) + len(chunk) <= self.max_segment_length:
                current += chunk
            else:
                packed.append(current)
                current = chunk

        if current:
            packed.append(current)

        return packed

    def _split_by_html_break(self, text: str) -> list[str]:
        parts = self._HTML_BREAK_RE.split(text)
        if len(parts) == 1:
            return [text] if text else []

        chunks: list[str] = []
        current = ""
        for part in parts:
            if not part:
                continue
            current += part
            if self._HTML_BREAK_RE.fullmatch(part):
                chunks.append(current)
                current = ""

        if current:
            chunks.append(current)

        return [chunk for chunk in chunks if chunk]

    def _split_by_whitespace(self, text: str) -> list[str]:
        chunks = re.findall(r"\S+\s*", text)
        if chunks:
            return chunks
        return [text] if text else []

    def _hard_split(self, text: str) -> list[str]:
        return [
            text[index : index + self.max_segment_length]
            for index in range(0, len(text), self.max_segment_length)
        ]

    def _all_within_limit(self, chunks: list[str]) -> bool:
        return all(len(chunk) <= self.max_segment_length for chunk in chunks)

    def _is_sentence_boundary(self, text: str, index: int) -> bool:
        char = text[index]
        if char in "。！？":
            return True
        if char not in ".!?":
            return False

        next_char = text[index + 1] if index + 1 < len(text) else ""
        if next_char == "":
            return True
        return next_char.isspace() or next_char in "\"')]}>"

    def _next_segment_id(self) -> str:
        segment_id = f"seg-{self._segment_counter:04d}"
        self._segment_counter += 1
        return segment_id
