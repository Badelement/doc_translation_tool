from __future__ import annotations

import re
from dataclasses import dataclass, field


_FENCE_START_RE = re.compile(r"^(```+|~~~+)")
_HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
_LIST_ITEM_RE = re.compile(r"^(\s*(?:[-*+]|\d+\.)\s+)(.*)$")
_ADMONITION_START_RE = re.compile(r"^:::(note|tip|warning)\s*$", re.IGNORECASE)
_ADMONITION_END_RE = re.compile(r"^:::\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")
_INLINE_PATTERN_RE = re.compile(
    r"(!\[(?P<image_alt>[^\]]*)\]\((?P<image_path>[^)]*)\))"
    r"|((?<!\!)\[(?P<link_text>[^\]]*)\]\((?P<link_target>[^)]*)\))"
    r"|((?P<code_ticks>`+)(?P<inline_code>[^\n]*?)(?P=code_ticks))"
)


@dataclass(slots=True)
class InlineToken:
    """Recognized inline Markdown element inside a block."""

    type: str
    raw: str
    text: str = ""
    target: str = ""


@dataclass(slots=True)
class MarkdownBlock:
    """Parsed block-level Markdown structure."""

    type: str
    raw_text: str
    lines: list[str]
    inline_tokens: list[InlineToken] = field(default_factory=list)
    meta: dict[str, str | int] = field(default_factory=dict)


@dataclass(slots=True)
class MarkdownDocument:
    """Full parsed Markdown document."""

    blocks: list[MarkdownBlock]
    trailing_newline: bool = False


class MarkdownParser:
    """Parser for the Markdown structures needed by the translation tool."""

    def parse(self, text: str) -> MarkdownDocument:
        lines = text.splitlines()
        blocks: list[MarkdownBlock] = []
        i = 0

        while i < len(lines):
            current_line = lines[i]

            if i == 0 and current_line.strip() == "---":
                block, i = self._consume_front_matter(lines, i)
                blocks.append(block)
                continue

            if self._is_fence_start(current_line):
                block, i = self._consume_fenced_code_block(lines, i)
                blocks.append(block)
                continue

            if self._is_admonition_start(current_line):
                block, i = self._consume_admonition_block(lines, i)
                blocks.append(block)
                continue

            if current_line.strip() == "":
                block, i = self._consume_blank_lines(lines, i)
                blocks.append(block)
                continue

            if self._is_table_start(lines, i):
                block, i = self._consume_table(lines, i)
                blocks.append(block)
                continue

            if self._is_heading(current_line):
                block, i = self._consume_heading(lines, i)
                blocks.append(block)
                continue

            if self._is_list_item(current_line):
                block, i = self._consume_list_item(lines, i)
                blocks.append(block)
                continue

            block, i = self._consume_paragraph(lines, i)
            blocks.append(block)

        return MarkdownDocument(
            blocks=blocks,
            trailing_newline=text.endswith("\n"),
        )

    def _consume_front_matter(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[MarkdownBlock, int]:
        collected = [lines[start_index]]
        i = start_index + 1
        while i < len(lines):
            collected.append(lines[i])
            if lines[i].strip() == "---":
                return (
                    MarkdownBlock(
                        type="front_matter",
                        raw_text="\n".join(collected),
                        lines=collected,
                    ),
                    i + 1,
                )
            i += 1

        return (
            MarkdownBlock(
                type="front_matter",
                raw_text="\n".join(collected),
                lines=collected,
            ),
            i,
        )

    def _consume_fenced_code_block(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[MarkdownBlock, int]:
        opening_line = lines[start_index]
        fence_marker = _FENCE_START_RE.match(opening_line)
        if fence_marker is None:
            raise ValueError(f"Expected fence marker in line: {opening_line}")
        fence = fence_marker.group(1)

        collected = [opening_line]
        i = start_index + 1
        while i < len(lines):
            collected.append(lines[i])
            if lines[i].startswith(fence[:3]):
                return (
                    MarkdownBlock(
                        type="fenced_code_block",
                        raw_text="\n".join(collected),
                        lines=collected,
                        meta={"fence": fence},
                    ),
                    i + 1,
                )
            i += 1

        return (
            MarkdownBlock(
                type="fenced_code_block",
                raw_text="\n".join(collected),
                lines=collected,
                meta={"fence": fence},
            ),
            i,
        )

    def _consume_admonition_block(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[MarkdownBlock, int]:
        start_line = lines[start_index]
        match = _ADMONITION_START_RE.match(start_line)
        if match is None:
            raise ValueError(f"Expected admonition marker in line: {start_line}")
        admonition_type = match.group(1).lower()

        collected = [start_line]
        i = start_index + 1
        while i < len(lines):
            collected.append(lines[i])
            if _ADMONITION_END_RE.match(lines[i]):
                return (
                    MarkdownBlock(
                        type="admonition",
                        raw_text="\n".join(collected),
                        lines=collected,
                        inline_tokens=self._parse_inline_tokens("\n".join(collected[1:-1])),
                        meta={"admonition_type": admonition_type},
                    ),
                    i + 1,
                )
            i += 1

        return (
            MarkdownBlock(
                type="admonition",
                raw_text="\n".join(collected),
                lines=collected,
                inline_tokens=self._parse_inline_tokens("\n".join(collected[1:])),
                meta={"admonition_type": admonition_type},
            ),
            i,
        )

    def _consume_blank_lines(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[MarkdownBlock, int]:
        collected: list[str] = []
        i = start_index
        while i < len(lines) and lines[i].strip() == "":
            collected.append(lines[i])
            i += 1

        return (
            MarkdownBlock(
                type="blank_line",
                raw_text="\n".join(collected),
                lines=collected,
            ),
            i,
        )

    def _consume_table(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[MarkdownBlock, int]:
        collected = [lines[start_index], lines[start_index + 1]]
        i = start_index + 2
        while i < len(lines):
            line = lines[i]
            if line.strip() == "" or "|" not in line:
                break
            collected.append(line)
            i += 1

        return (
            MarkdownBlock(
                type="table",
                raw_text="\n".join(collected),
                lines=collected,
            ),
            i,
        )

    def _consume_heading(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[MarkdownBlock, int]:
        line = lines[start_index]
        match = _HEADING_RE.match(line)
        if match is None:
            raise ValueError(f"Expected heading marker in line: {line}")
        level = len(match.group(1))
        text = match.group(2)

        return (
            MarkdownBlock(
                type="heading",
                raw_text=line,
                lines=[line],
                inline_tokens=self._parse_inline_tokens(text),
                meta={"level": level},
            ),
            start_index + 1,
        )

    def _consume_list_item(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[MarkdownBlock, int]:
        line = lines[start_index]
        match = _LIST_ITEM_RE.match(line)
        if match is None:
            raise ValueError(f"Expected list item marker in line: {line}")
        marker = match.group(1)
        text = match.group(2)

        return (
            MarkdownBlock(
                type="list_item",
                raw_text=line,
                lines=[line],
                inline_tokens=self._parse_inline_tokens(text),
                meta={"marker": marker},
            ),
            start_index + 1,
        )

    def _consume_paragraph(
        self,
        lines: list[str],
        start_index: int,
    ) -> tuple[MarkdownBlock, int]:
        collected: list[str] = []
        i = start_index
        while i < len(lines):
            line = lines[i]
            if line.strip() == "":
                break
            if self._is_fence_start(line):
                break
            if self._is_admonition_start(line):
                break
            if self._is_heading(line):
                break
            if self._is_table_start(lines, i):
                break
            if collected and self._is_list_item(line):
                break
            collected.append(line)
            i += 1

        raw_text = "\n".join(collected)
        return (
            MarkdownBlock(
                type="paragraph",
                raw_text=raw_text,
                lines=collected,
                inline_tokens=self._parse_inline_tokens(raw_text),
            ),
            i,
        )

    def _parse_inline_tokens(self, text: str) -> list[InlineToken]:
        tokens: list[InlineToken] = []
        cursor = 0
        for match in _INLINE_PATTERN_RE.finditer(text):
            if match.start() > cursor:
                literal = text[cursor : match.start()]
                if literal:
                    tokens.append(InlineToken(type="text", raw=literal, text=literal))

            full_match = match.group(0)
            if match.group("image_alt") is not None:
                tokens.append(
                    InlineToken(
                        type="image",
                        raw=full_match,
                        text=match.group("image_alt"),
                        target=match.group("image_path"),
                    )
                )
            elif match.group("link_text") is not None:
                tokens.append(
                    InlineToken(
                        type="link",
                        raw=full_match,
                        text=match.group("link_text"),
                        target=match.group("link_target"),
                    )
                )
            elif match.group("inline_code") is not None:
                tokens.append(
                    InlineToken(
                        type="inline_code",
                        raw=full_match,
                        text=match.group("inline_code"),
                    )
                )
            cursor = match.end()

        if cursor < len(text):
            literal = text[cursor:]
            if literal:
                tokens.append(InlineToken(type="text", raw=literal, text=literal))

        return tokens

    def _is_fence_start(self, line: str) -> bool:
        return _FENCE_START_RE.match(line) is not None

    def _is_heading(self, line: str) -> bool:
        return _HEADING_RE.match(line) is not None

    def _is_list_item(self, line: str) -> bool:
        return _LIST_ITEM_RE.match(line) is not None

    def _is_admonition_start(self, line: str) -> bool:
        return _ADMONITION_START_RE.match(line) is not None

    def _is_table_start(self, lines: list[str], index: int) -> bool:
        if index + 1 >= len(lines):
            return False
        return "|" in lines[index] and _TABLE_SEPARATOR_RE.match(lines[index + 1]) is not None
