from __future__ import annotations

import re
from dataclasses import dataclass, field

from doc_translation_tool.markdown.parser import MarkdownBlock, MarkdownDocument, MarkdownParser


_FRONT_MATTER_KEY_VALUE_RE = re.compile(r"^(\s*)([A-Za-z0-9_-]+):(\s*)(.*)$")
_FRONT_MATTER_BLOCK_START_RE = re.compile(r"^(\s*)([A-Za-z0-9_-]+):(\s*)([|>][-+]?)\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")
_HTML_XML_TAG_RE = re.compile(r"</?[A-Za-z][A-Za-z0-9:_-]*(?:\s+[^<>\n]*?)?\s*/?>")
_FILE_LIKE_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9._-]*\.(?:"
    r"dts|dtbo|cfg|conf|mk|ko|sh|xml|json|h|c|cc|cpp|hpp|py|txt|bin|img|rc"
    r")\b"
)
_PATH_LIKE_RE = re.compile(
    r"(?<![@\w])(?:[A-Za-z]:\\|\.{1,2}/|/)"
    r"(?:[A-Za-z0-9{}_.-]+(?:\\|/))+[A-Za-z0-9{}_.-]+"
)
_UPPER_CONSTANT_RE = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b")


@dataclass(slots=True)
class ProtectedPlaceholder:
    """Protected raw content replaced by a stable placeholder token."""

    token: str
    raw_text: str
    kind: str


@dataclass(slots=True)
class ProtectedMarkdownBlock:
    """Markdown block after protected content has been replaced by placeholders."""

    block_type: str
    protected_text: str
    placeholders: list[ProtectedPlaceholder] = field(default_factory=list)
    translatable: bool = True
    meta: dict[str, str | int] = field(default_factory=dict)


@dataclass(slots=True)
class ProtectedMarkdownDocument:
    """Markdown document with protected placeholders ready for later translation steps."""

    blocks: list[ProtectedMarkdownBlock]
    trailing_newline: bool = False


class MarkdownProtector:
    """Protect code, inline code, and Markdown targets that must not be translated."""

    def __init__(
        self,
        *,
        translatable_front_matter_fields: set[str] | list[str] | tuple[str, ...] | None = None,
    ) -> None:
        self._placeholder_index = 0
        fields = translatable_front_matter_fields or {"title", "subtitle", "desc"}
        self.translatable_front_matter_fields = {field.lower() for field in fields}
        self._parser = MarkdownParser()

    def protect(self, document: MarkdownDocument) -> ProtectedMarkdownDocument:
        blocks: list[ProtectedMarkdownBlock] = []
        for block in document.blocks:
            blocks.append(self._protect_block(block))
        return ProtectedMarkdownDocument(
            blocks=blocks,
            trailing_newline=document.trailing_newline,
        )

    def restore_text(
        self,
        text: str,
        placeholders: list[ProtectedPlaceholder],
    ) -> str:
        restored = text
        for placeholder in placeholders:
            restored = restored.replace(placeholder.token, placeholder.raw_text)
        return restored

    def restore_block_text(self, block: ProtectedMarkdownBlock) -> str:
        return self.restore_text(block.protected_text, block.placeholders)

    def restore_document(
        self,
        document: ProtectedMarkdownDocument,
        translated_block_texts: list[str] | None = None,
    ) -> str:
        if translated_block_texts is not None and len(translated_block_texts) != len(document.blocks):
            raise ValueError("Translated block text count must match protected block count.")

        restored_blocks: list[str] = []
        for index, block in enumerate(document.blocks):
            source_text = (
                translated_block_texts[index]
                if translated_block_texts is not None
                else block.protected_text
            )
            restored_blocks.append(self.restore_text(source_text, block.placeholders))

        restored = "\n".join(restored_blocks)
        if document.trailing_newline:
            restored += "\n"
        return restored

    def _protect_block(self, block: MarkdownBlock) -> ProtectedMarkdownBlock:
        if block.type == "front_matter":
            return self._protect_front_matter_block(block)

        if block.type == "fenced_code_block":
            placeholder = self._create_placeholder(block.raw_text, "fenced_code_block")
            return ProtectedMarkdownBlock(
                block_type=block.type,
                protected_text=placeholder.token,
                placeholders=[placeholder],
                translatable=False,
                meta=dict(block.meta),
            )

        if block.type == "table":
            return self._protect_table_block(block)

        if block.type == "heading":
            prefix = "#" * int(block.meta["level"]) + " "
            content, placeholders = self._protect_inline_content(block.inline_tokens)
            return ProtectedMarkdownBlock(
                block_type=block.type,
                protected_text=f"{prefix}{content}",
                placeholders=placeholders,
                meta=dict(block.meta),
            )

        if block.type == "list_item":
            marker = str(block.meta["marker"])
            content, placeholders = self._protect_inline_content(block.inline_tokens)
            return ProtectedMarkdownBlock(
                block_type=block.type,
                protected_text=f"{marker}{content}",
                placeholders=placeholders,
                meta=dict(block.meta),
            )

        if block.type == "paragraph":
            content, placeholders = self._protect_inline_content(block.inline_tokens)
            return ProtectedMarkdownBlock(
                block_type=block.type,
                protected_text=content,
                placeholders=placeholders,
                meta=dict(block.meta),
            )

        if block.type == "admonition":
            start_line = block.lines[0]
            has_end = len(block.lines) >= 2 and block.lines[-1].strip() == ":::"
            body_content, placeholders = self._protect_inline_content(block.inline_tokens)
            parts = [start_line]
            if body_content:
                parts.append(body_content)
            if has_end:
                parts.append(":::")
            return ProtectedMarkdownBlock(
                block_type=block.type,
                protected_text="\n".join(parts),
                placeholders=placeholders,
                meta=dict(block.meta),
            )

        return ProtectedMarkdownBlock(
            block_type=block.type,
            protected_text=block.raw_text,
            placeholders=[],
            translatable=block.type not in {"blank_line"},
            meta=dict(block.meta),
        )

    def _protect_front_matter_block(self, block: MarkdownBlock) -> ProtectedMarkdownBlock:
        lines = block.lines
        if not lines:
            return ProtectedMarkdownBlock(
                block_type=block.type,
                protected_text=block.raw_text,
                placeholders=[],
                translatable=False,
                meta=dict(block.meta),
            )

        placeholders: list[ProtectedPlaceholder] = []
        protected_lines = [lines[0]]
        has_translatable_content = False
        index = 1

        while index < len(lines) - 1:
            line = lines[index]
            block_start = _FRONT_MATTER_BLOCK_START_RE.match(line)
            if block_start is not None:
                key = block_start.group(2).lower()
                key_indent = len(block_start.group(1))
                if key in self.translatable_front_matter_fields:
                    placeholder = self._create_placeholder(line, "front_matter_key")
                    placeholders.append(placeholder)
                    protected_lines.append(placeholder.token)
                    index += 1

                    while (
                        index < len(lines) - 1
                        and self._is_front_matter_block_value_line(lines[index], key_indent)
                    ):
                        body_line = lines[index]
                        if body_line.strip() == "":
                            blank_placeholder = self._create_placeholder(
                                body_line,
                                "front_matter_blank_line",
                            )
                            placeholders.append(blank_placeholder)
                            protected_lines.append(blank_placeholder.token)
                        else:
                            indent_length = len(body_line) - len(body_line.lstrip(" "))
                            indent = body_line[:indent_length]
                            content = body_line[indent_length:]
                            indent_placeholder = self._create_placeholder(
                                indent,
                                "front_matter_indent",
                            )
                            placeholders.append(indent_placeholder)
                            protected_lines.append(indent_placeholder.token + content)
                            if content.strip():
                                has_translatable_content = True
                        index += 1
                    continue

                index = self._append_non_translatable_front_matter_block(
                    lines,
                    index,
                    key_indent=key_indent,
                    protected_lines=protected_lines,
                    placeholders=placeholders,
                )
                continue

            key_value = _FRONT_MATTER_KEY_VALUE_RE.match(line)
            if key_value is not None:
                key = key_value.group(2).lower()
                if key in self.translatable_front_matter_fields and key_value.group(4).strip():
                    prefix = f"{key_value.group(1)}{key_value.group(2)}:{key_value.group(3)}"
                    prefix_placeholder = self._create_placeholder(prefix, "front_matter_key")
                    placeholders.append(prefix_placeholder)
                    protected_lines.append(prefix_placeholder.token + key_value.group(4))
                    has_translatable_content = True
                else:
                    line_placeholder = self._create_placeholder(line, "front_matter_line")
                    placeholders.append(line_placeholder)
                    protected_lines.append(line_placeholder.token)
                index += 1
                continue

            raw_placeholder = self._create_placeholder(line, "front_matter_line")
            placeholders.append(raw_placeholder)
            protected_lines.append(raw_placeholder.token)
            index += 1

        if len(lines) >= 2:
            protected_lines.append(lines[-1])

        return ProtectedMarkdownBlock(
            block_type=block.type,
            protected_text="\n".join(protected_lines),
            placeholders=placeholders,
            translatable=has_translatable_content,
            meta=dict(block.meta),
        )

    def _protect_table_block(self, block: MarkdownBlock) -> ProtectedMarkdownBlock:
        placeholders: list[ProtectedPlaceholder] = []
        protected_lines: list[str] = []
        has_translatable_content = False

        for index, line in enumerate(block.lines):
            if index == 1 and _TABLE_SEPARATOR_RE.match(line) is not None:
                separator_placeholder = self._create_placeholder(line, "table_separator")
                placeholders.append(separator_placeholder)
                protected_lines.append(separator_placeholder.token)
                continue

            protected_line, line_placeholders, line_has_text = self._protect_table_row(line)
            placeholders.extend(line_placeholders)
            protected_lines.append(protected_line)
            has_translatable_content = has_translatable_content or line_has_text

        return ProtectedMarkdownBlock(
            block_type=block.type,
            protected_text="\n".join(protected_lines),
            placeholders=placeholders,
            translatable=has_translatable_content,
            meta=dict(block.meta),
        )

    def _append_non_translatable_front_matter_block(
        self,
        lines: list[str],
        index: int,
        *,
        key_indent: int,
        protected_lines: list[str],
        placeholders: list[ProtectedPlaceholder],
    ) -> int:
        line_placeholder = self._create_placeholder(lines[index], "front_matter_line")
        placeholders.append(line_placeholder)
        protected_lines.append(line_placeholder.token)
        index += 1

        while index < len(lines) - 1 and self._is_front_matter_block_value_line(lines[index], key_indent):
            body_placeholder = self._create_placeholder(lines[index], "front_matter_line")
            placeholders.append(body_placeholder)
            protected_lines.append(body_placeholder.token)
            index += 1

        return index

    def _is_front_matter_block_value_line(self, line: str, key_indent: int) -> bool:
        if line.strip() == "":
            return True
        indent_length = len(line) - len(line.lstrip(" "))
        return indent_length > key_indent

    def _protect_table_row(
        self,
        line: str,
    ) -> tuple[str, list[ProtectedPlaceholder], bool]:
        protected_parts: list[str] = []
        placeholders: list[ProtectedPlaceholder] = []
        has_translatable_content = False

        for part in self._split_table_line(line):
            if part == "|":
                pipe_placeholder = self._create_placeholder(part, "table_pipe")
                placeholders.append(pipe_placeholder)
                protected_parts.append(pipe_placeholder.token)
                continue

            inline_content, inline_placeholders = self._protect_inline_text(part)
            placeholders.extend(inline_placeholders)
            protected_parts.append(inline_content)
            if part.strip():
                has_translatable_content = True

        return "".join(protected_parts), placeholders, has_translatable_content

    def _protect_inline_text(self, text: str) -> tuple[str, list[ProtectedPlaceholder]]:
        if not text:
            return "", []

        parsed = self._parser.parse(text)
        if not parsed.blocks:
            return text, []

        return self._protect_inline_content(parsed.blocks[0].inline_tokens)

    def _split_table_line(self, line: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        escaped = False

        for char in line:
            if char == "|" and not escaped:
                parts.append("".join(current))
                parts.append(char)
                current = []
                continue

            current.append(char)
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True

        parts.append("".join(current))
        return parts

    def _protect_inline_content(self, inline_tokens) -> tuple[str, list[ProtectedPlaceholder]]:
        protected_parts: list[str] = []
        placeholders: list[ProtectedPlaceholder] = []

        for token in inline_tokens:
            if token.type == "text":
                protected_text, text_placeholders = self._protect_embedded_markup(token.raw)
                protected_text, literal_placeholders = self._protect_embedded_technical_literals(
                    protected_text
                )
                placeholders.extend(text_placeholders)
                placeholders.extend(literal_placeholders)
                protected_parts.append(protected_text)
                continue

            if token.type == "inline_code":
                placeholder = self._create_placeholder(token.raw, "inline_code")
                placeholders.append(placeholder)
                protected_parts.append(placeholder.token)
                continue

            if token.type == "image":
                placeholder = self._create_placeholder(token.target, "image_path")
                placeholders.append(placeholder)
                protected_parts.append(f"![{token.text}]({placeholder.token})")
                continue

            if token.type == "link":
                placeholder = self._create_placeholder(token.target, "link_target")
                placeholders.append(placeholder)
                protected_parts.append(f"[{token.text}]({placeholder.token})")
                continue

            protected_parts.append(token.raw)

        return "".join(protected_parts), placeholders

    def _protect_embedded_markup(self, text: str) -> tuple[str, list[ProtectedPlaceholder]]:
        if not text:
            return "", []

        protected_parts: list[str] = []
        placeholders: list[ProtectedPlaceholder] = []
        last_index = 0

        for match in _HTML_XML_TAG_RE.finditer(text):
            protected_parts.append(text[last_index : match.start()])
            raw_tag = match.group(0)
            if raw_tag.lower() in {"<br>", "<br/>", "<br />"}:
                protected_parts.append(raw_tag)
            else:
                placeholder = self._create_placeholder(raw_tag, "html_xml_tag")
                placeholders.append(placeholder)
                protected_parts.append(placeholder.token)
            last_index = match.end()

        protected_parts.append(text[last_index:])
        return "".join(protected_parts), placeholders

    def _protect_embedded_technical_literals(
        self,
        text: str,
    ) -> tuple[str, list[ProtectedPlaceholder]]:
        if not text:
            return "", []

        protected_text = text
        placeholders: list[ProtectedPlaceholder] = []

        for pattern, kind in (
            (_PATH_LIKE_RE, "path_literal"),
            (_FILE_LIKE_RE, "file_literal"),
            (_UPPER_CONSTANT_RE, "upper_constant_literal"),
        ):
            protected_text, new_placeholders = self._replace_matches_with_placeholders(
                protected_text,
                pattern,
                kind,
            )
            placeholders.extend(new_placeholders)

        return protected_text, placeholders

    def _replace_matches_with_placeholders(
        self,
        text: str,
        pattern: re.Pattern[str],
        kind: str,
    ) -> tuple[str, list[ProtectedPlaceholder]]:
        placeholders: list[ProtectedPlaceholder] = []
        protected_parts: list[str] = []
        last_index = 0

        for match in pattern.finditer(text):
            if self._is_inside_placeholder_token(text, match.start(), match.end()):
                continue
            protected_parts.append(text[last_index : match.start()])
            placeholder = self._create_placeholder(match.group(0), kind)
            placeholders.append(placeholder)
            protected_parts.append(placeholder.token)
            last_index = match.end()

        protected_parts.append(text[last_index:])
        return "".join(protected_parts), placeholders

    def _is_inside_placeholder_token(self, text: str, start: int, end: int) -> bool:
        return (
            start >= 2
            and end + 2 <= len(text)
            and text[start - 2 : start] == "@@"
            and text[end : end + 2] == "@@"
        )

    def _create_placeholder(self, raw_text: str, kind: str) -> ProtectedPlaceholder:
        token = f"@@PROTECT_{self._placeholder_index:04d}@@"
        self._placeholder_index += 1
        return ProtectedPlaceholder(token=token, raw_text=raw_text, kind=kind)
