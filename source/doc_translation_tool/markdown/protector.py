from __future__ import annotations

import re
from dataclasses import dataclass, field

from doc_translation_tool.markdown.parser import MarkdownBlock, MarkdownDocument, MarkdownParser
from doc_translation_tool.utils.text_utils import (
    HTML_TAG_PATTERN,
    PATH_PATTERN,
    UPPER_CONSTANT_PATTERN,
    extract_file_references,
)


_FRONT_MATTER_KEY_VALUE_RE = re.compile(r"^(\s*)([A-Za-z0-9_-]+):(\s*)(.*)$")
_FRONT_MATTER_BLOCK_START_RE = re.compile(r"^(\s*)([A-Za-z0-9_-]+):(\s*)([|>][-+]?)\s*$")
_TABLE_SEPARATOR_RE = re.compile(r"^\s*\|?(?:\s*:?-+:?\s*\|)+\s*:?-+:?\s*\|?\s*$")
_FENCE_LANGUAGE_RE = re.compile(r"^[`~]{3,}\s*(\w+)?")
_WHITESPACE_SUFFIX_RE = re.compile(r"^(.*?)([ \t]*)$", re.DOTALL)

# Use optimized pre-compiled patterns from utils
_HTML_XML_TAG_RE = HTML_TAG_PATTERN
_PATH_LIKE_RE = PATH_PATTERN
_UPPER_CONSTANT_RE = UPPER_CONSTANT_PATTERN

# Comment patterns for different programming languages
# Each pattern should capture the comment prefix and the comment content
# Patterns use MULTILINE flag to find comments anywhere on the line

# Shared pattern instances to reduce memory usage
_HASH_COMMENT_PATTERN = [(re.compile(r"(#)(.*)$", re.MULTILINE), "#")]
_SLASH_COMMENT_PATTERN = [
    (re.compile(r"(//)(.*)$", re.MULTILINE), "//"),
    (re.compile(r"(/\*)(.*?)(\*/)", re.DOTALL), "/*"),
]
_HTML_COMMENT_PATTERN = [(re.compile(r"(<!--)(.*?)(-->)", re.DOTALL), "<!--")]

_COMMENT_PATTERNS: dict[str, list[tuple[re.Pattern[str], str]]] = {
    # Python, Ruby, Shell, YAML, etc. - all use # comments
    **{lang: _HASH_COMMENT_PATTERN for lang in [
        "python", "py", "ruby", "rb", "shell", "sh", "bash", "zsh",
        "yaml", "yml", "conf", "cfg", "mk", "makefile", "dockerfile",
        "perl", "pl", "r", "tcl"
    ]},
    # C/C++, Java, JavaScript, Go, etc. - all use // and /* */ comments
    **{lang: _SLASH_COMMENT_PATTERN for lang in [
        "c", "cpp", "cc", "h", "hpp", "java", "javascript", "js",
        "typescript", "ts", "go", "rust", "rs", "swift", "kotlin", "kt",
        "csharp", "cs", "php", "scala", "groovy", "dart"
    ]},
    # HTML, XML, etc. - all use <!-- --> comments
    **{lang: _HTML_COMMENT_PATTERN for lang in [
        "html", "xml", "svg", "markdown", "md"
    ]},
}

# Default comment patterns for unknown languages (use # style)
_DEFAULT_COMMENT_PATTERNS: list[tuple[re.Pattern[str], str]] = _HASH_COMMENT_PATTERN


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
            return self._protect_code_block_with_comments(block)

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
                            indent, content = self._split_leading_indentation(body_line)
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
        if line.startswith("\t"):
            return True
        indent_length = len(line) - len(line.lstrip(" "))
        return indent_length > key_indent

    def _split_leading_indentation(self, line: str) -> tuple[str, str]:
        stripped = line.lstrip(" \t")
        indent_length = len(line) - len(stripped)
        return line[:indent_length], stripped

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
        if not line:
            return [""]

        parts: list[str] = []
        current_start = 0
        escaped = False
        i = 0

        while i < len(line):
            char = line[i]
            if char == "|" and not escaped:
                parts.append(line[current_start:i])
                parts.append(char)
                current_start = i + 1
            elif char == "\\" and not escaped:
                escaped = True
            else:
                escaped = False
            i += 1

        parts.append(line[current_start:])
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

        # Protect file references first so trailing sentence punctuation stays outside
        # placeholders and later path matching does not consume it.
        protected_text, file_placeholders = self._protect_file_references(protected_text)
        placeholders.extend(file_placeholders)

        # Protect paths and constants using regex patterns
        for pattern, kind in (
            (_PATH_LIKE_RE, "path_literal"),
            (_UPPER_CONSTANT_RE, "upper_constant_literal"),
        ):
            protected_text, new_placeholders = self._replace_matches_with_placeholders(
                protected_text,
                pattern,
                kind,
            )
            placeholders.extend(new_placeholders)

        return protected_text, placeholders

    def _protect_file_references(
        self,
        text: str,
    ) -> tuple[str, list[ProtectedPlaceholder]]:
        """Protect file references using optimized string matching instead of regex.

        This avoids the performance cost of complex regex backtracking.
        """
        placeholders: list[ProtectedPlaceholder] = []
        file_refs = extract_file_references(text)

        if not file_refs:
            return text, placeholders

        # Process from end to start to maintain positions
        protected_text = text
        for start, end, matched_text in reversed(file_refs):
            if self._is_inside_placeholder_token(protected_text, start, end):
                continue
            placeholder = self._create_placeholder(matched_text, "file_literal")
            placeholders.append(placeholder)
            protected_text = (
                protected_text[:start] + placeholder.token + protected_text[end:]
            )

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

    def _extract_code_language(self, block: MarkdownBlock) -> str | None:
        """Extract the language identifier from the code block fence line."""
        if not block.lines:
            return None
        fence_line = block.lines[0].strip()
        # Match ```python or ~~~python
        match = _FENCE_LANGUAGE_RE.match(fence_line)
        if match:
            return match.group(1)
        return None

    def _protect_code_block_with_comments(self, block: MarkdownBlock) -> ProtectedMarkdownBlock:
        """Protect code block while extracting comments for translation.

        The code itself is protected with placeholders, but comments are exposed
        as translatable text with their prefixes/suffixes preserved.
        """
        language = self._extract_code_language(block)
        if not language:
            # No language specified, treat as plain code block without comment extraction
            placeholder = self._create_placeholder(block.raw_text, "fenced_code_block")
            return ProtectedMarkdownBlock(
                block_type=block.type,
                protected_text=placeholder.token,
                placeholders=[placeholder],
                translatable=False,
                meta=dict(block.meta),
            )

        language_lower = language.lower()
        comment_patterns = _COMMENT_PATTERNS.get(language_lower, _DEFAULT_COMMENT_PATTERNS)

        # Separate line comment patterns from block comment patterns
        line_patterns = [(p, t) for p, t in comment_patterns if t in ("#", "//")]
        block_patterns = [(p, t) for p, t in comment_patterns if t in ("/*", "<!--")]

        # Process each line to extract comments
        placeholders: list[ProtectedPlaceholder] = []
        protected_lines: list[str] = []
        has_translatable_content = False

        # First line is the fence (e.g., ```python)
        fence_line = block.lines[0]
        fence_placeholder = self._create_placeholder(fence_line, "code_fence")
        placeholders.append(fence_placeholder)
        protected_lines.append(fence_placeholder.token)

        # Process content lines (excluding first and last fence lines)
        content_lines = block.lines[1:-1] if len(block.lines) > 2 else []
        closing_fence = block.lines[-1] if len(block.lines) > 1 else ""

        # Process content as a whole for block comments, then line by line
        if block_patterns:
            # First handle block comments on the entire content
            content_text = "\n".join(content_lines)
            content_result = self._process_code_content_with_block_comments(
                content_text, block_patterns, line_patterns
            )
            protected_lines.extend(content_result["lines"])
            placeholders.extend(content_result["placeholders"])
            if content_result["has_comment"]:
                has_translatable_content = True
        else:
            # Process line by line for line comments only
            for line in content_lines:
                line_result = self._process_code_line(line, line_patterns)
                protected_line = "".join(line_result["parts"])
                protected_lines.append(protected_line)
                placeholders.extend(line_result["placeholders"])
                if line_result["has_comment"]:
                    has_translatable_content = True

        # Last line is the closing fence
        if closing_fence:
            closing_placeholder = self._create_placeholder(closing_fence, "code_fence")
            placeholders.append(closing_placeholder)
            protected_lines.append(closing_placeholder.token)

        return ProtectedMarkdownBlock(
            block_type=block.type,
            protected_text="\n".join(protected_lines),
            placeholders=placeholders,
            translatable=has_translatable_content,
            meta={**dict(block.meta), "language": language_lower},
        )

    def _process_code_line(
        self,
        line: str,
        comment_patterns: list[tuple[re.Pattern[str], str]],
    ) -> dict[str, any]:
        """Process a single code line to extract comments.

        Returns a dict with:
        - parts: list of strings to join for the protected text
        - placeholders: list of ProtectedPlaceholder objects
        - has_comment: whether this line has translatable comment content
        """
        placeholders: list[ProtectedPlaceholder] = []
        parts: list[str] = []
        has_comment = False

        # Try each comment pattern
        for pattern, prefix in comment_patterns:
            match = pattern.search(line)
            if match:
                # Found a comment
                if prefix in ("#", "//"):
                    # Line comment: prefix is protected, content is translatable
                    prefix_text = match.group(1)
                    comment_content = match.group(2)

                    # Protect the code part before the comment
                    code_part = line[:match.start()]
                    if code_part:
                        code_placeholder = self._create_placeholder(code_part, "code_line_prefix")
                        placeholders.append(code_placeholder)
                        parts.append(code_placeholder.token)

                    # Protect the comment prefix
                    prefix_placeholder = self._create_placeholder(prefix_text, "comment_prefix")
                    placeholders.append(prefix_placeholder)
                    parts.append(prefix_placeholder.token)

                    # Comment content is translatable (keep as-is in protected text)
                    if comment_content:
                        parts.append(comment_content)
                        has_comment = True

                    return {
                        "parts": parts,
                        "placeholders": placeholders,
                        "has_comment": has_comment,
                    }

                elif prefix == "/*":
                    # C-style block comment
                    # Protect everything except the comment content
                    before = line[:match.start()]
                    comment_start = match.group(1)  # /*
                    comment_content = match.group(2)  # content
                    comment_end = match.group(3)  # */
                    after = line[match.end():]

                    if before:
                        before_placeholder = self._create_placeholder(before, "code_before_comment")
                        placeholders.append(before_placeholder)
                        parts.append(before_placeholder.token)

                    start_placeholder = self._create_placeholder(comment_start, "comment_start")
                    placeholders.append(start_placeholder)
                    parts.append(start_placeholder.token)

                    if comment_content:
                        parts.append(comment_content)
                        has_comment = True

                    end_placeholder = self._create_placeholder(comment_end, "comment_end")
                    placeholders.append(end_placeholder)
                    parts.append(end_placeholder.token)

                    if after:
                        after_placeholder = self._create_placeholder(after, "code_after_comment")
                        placeholders.append(after_placeholder)
                        parts.append(after_placeholder.token)

                    return {
                        "parts": parts,
                        "placeholders": placeholders,
                        "has_comment": has_comment,
                    }

                elif prefix == "<!--":
                    # HTML-style comment
                    before = line[:match.start()]
                    comment_start = match.group(1)  # <!--
                    comment_content = match.group(2)  # content
                    comment_end = match.group(3)  # -->
                    after = line[match.end():]

                    if before:
                        before_placeholder = self._create_placeholder(before, "code_before_comment")
                        placeholders.append(before_placeholder)
                        parts.append(before_placeholder.token)

                    start_placeholder = self._create_placeholder(comment_start, "comment_start")
                    placeholders.append(start_placeholder)
                    parts.append(start_placeholder.token)

                    if comment_content:
                        parts.append(comment_content)
                        has_comment = True

                    end_placeholder = self._create_placeholder(comment_end, "comment_end")
                    placeholders.append(end_placeholder)
                    parts.append(end_placeholder.token)

                    if after:
                        after_placeholder = self._create_placeholder(after, "code_after_comment")
                        placeholders.append(after_placeholder)
                        parts.append(after_placeholder.token)

                    return {
                        "parts": parts,
                        "placeholders": placeholders,
                        "has_comment": has_comment,
                    }

        # No comment found, protect the entire line
        if line:
            line_placeholder = self._create_placeholder(line, "code_line")
            placeholders.append(line_placeholder)
            parts.append(line_placeholder.token)

        return {
            "parts": parts,
            "placeholders": placeholders,
            "has_comment": has_comment,
        }

    def _process_code_content_with_block_comments(
        self,
        content: str,
        block_patterns: list[tuple[re.Pattern[str], str]],
        line_patterns: list[tuple[re.Pattern[str], str]],
    ) -> dict[str, any]:
        """Process code content that may contain block comments spanning multiple lines.

        Returns a dict with:
        - lines: list of protected line strings
        - placeholders: list of ProtectedPlaceholder objects
        - has_comment: whether any translatable comment content was found
        """
        placeholders: list[ProtectedPlaceholder] = []
        lines: list[str] = []
        has_comment = False

        # First, find all block comments and protect them
        protected_content = content
        block_comment_matches: list[tuple[int, int, str, str, str]] = []  # start, end, start_marker, content, end_marker

        for pattern, prefix in block_patterns:
            for match in pattern.finditer(protected_content):
                block_comment_matches.append((
                    match.start(),
                    match.end(),
                    match.group(1),  # /* or <!--
                    match.group(2),  # content
                    match.group(3),  # */ or -->
                ))

        if not block_comment_matches:
            # No block comments, process line by line with line patterns
            for line in content.split("\n"):
                line_result = self._process_code_line(line, line_patterns)
                protected_line = "".join(line_result["parts"])
                lines.append(protected_line)
                placeholders.extend(line_result["placeholders"])
                if line_result["has_comment"]:
                    has_comment = True
            return {"lines": lines, "placeholders": placeholders, "has_comment": has_comment}

        # Sort matches by start position
        block_comment_matches.sort(key=lambda x: x[0])

        # Merge overlapping matches (keep the first one)
        merged_matches: list[tuple[int, int, str, str, str]] = []
        for match in block_comment_matches:
            if not merged_matches or match[0] >= merged_matches[-1][1]:
                merged_matches.append(match)

        # Process content with block comments
        last_end = 0

        for start, end, start_marker, comment_content, end_marker in merged_matches:
            # Process code before this block comment
            before = protected_content[last_end:start]
            # Capture any trailing whitespace/indentation before the block comment
            # The indentation is spaces/tabs on the same line as /*
            before_match = _WHITESPACE_SUFFIX_RE.match(before)
            if before_match is None:
                # Fallback: treat entire content as before_content with no indent
                before_content = before
                before_indent = ""
            else:
                before_content = before_match.group(1)
                before_indent = before_match.group(2)

            if before_content:
                # Process each line in the before section for line comments
                before_lines = before_content.split("\n")
                for i, line in enumerate(before_lines):
                    is_last_line = i == len(before_lines) - 1
                    if is_last_line and not line.strip():
                        # Skip empty last line (trailing newline)
                        break
                    line_result = self._process_code_line(line, line_patterns)
                    protected_line = "".join(line_result["parts"])
                    lines.append(protected_line)
                    placeholders.extend(line_result["placeholders"])
                    if line_result["has_comment"]:
                        has_comment = True

            # Process the block comment
            start_placeholder = self._create_placeholder(start_marker, "block_comment_start")
            placeholders.append(start_placeholder)

            if comment_content:
                has_comment = True
                # Block comment content may span multiple lines - keep as is for translation
                comment_lines = comment_content.split("\n")
                # The indentation goes BEFORE the /* marker
                first_line = before_indent + start_placeholder.token + comment_lines[0]
                if len(comment_lines) == 1:
                    # Single line block comment
                    lines.append(first_line)
                else:
                    # Multi-line block comment
                    lines.append(first_line)
                    for comment_line in comment_lines[1:]:
                        lines.append(comment_line)
            else:
                lines.append(before_indent + start_placeholder.token)

            end_placeholder = self._create_placeholder(end_marker, "block_comment_end")
            placeholders.append(end_placeholder)
            # Append end marker to the last line
            if lines:
                lines[-1] = lines[-1] + end_placeholder.token
            else:
                lines.append(end_placeholder.token)

            last_end = end

        # Process remaining content after last block comment
        after = protected_content[last_end:]
        if after:
            for line in after.split("\n"):
                if line:  # Skip empty trailing line
                    line_result = self._process_code_line(line, line_patterns)
                    protected_line = "".join(line_result["parts"])
                    lines.append(protected_line)
                    placeholders.extend(line_result["placeholders"])
                    if line_result["has_comment"]:
                        has_comment = True

        return {"lines": lines, "placeholders": placeholders, "has_comment": has_comment}
