from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Iterable
import xml.etree.ElementTree as ET

from doc_translation_tool.config import AppSettings
from doc_translation_tool.documents.base import (
    DocumentHandler,
    DocumentParseError,
    DocumentSegment,
    PreparedDocument,
    PreparedDocumentBlock,
)
from doc_translation_tool.documents.types import DITA_DOCUMENT_TYPE

_URL_LIKE_RE = re.compile(r"https?://[^\s<>()]+")
_FILE_LIKE_RE = re.compile(
    r"\b[A-Za-z0-9][A-Za-z0-9._-]*\.(?:"
    r"dts|dtbo|cfg|conf|ini|yaml|yml|toml|mk|ko|sh|xml|json|html|pdf|"
    r"h|c|cc|cpp|hpp|py|txt|bin|img|rc|dll|so|log|csv|md|dita"
    r")\b"
)
_PATH_LIKE_RE = re.compile(
    r"(?<![@\w])(?:"
    r"[A-Za-z]:\\(?:[A-Za-z0-9{}_.-]+\\)*[A-Za-z0-9{}_.-]+"
    r"|(?:\.{1,2}[\\/]|/)(?:[A-Za-z0-9{}_.-]+[\\/])*[A-Za-z0-9{}_.-]+"
    r"|(?:[A-Za-z0-9{}_.-]+[\\/])+[A-Za-z0-9{}_.-]+"
    r")"
)
_UPPER_CONSTANT_RE = re.compile(r"\b[A-Z][A-Z0-9]+(?:_[A-Z0-9]+)+\b")
_LEADING_XML_MISC_RE = re.compile(
    r"\A(?P<prefix>\s*(?:(?:<\?xml[\s\S]*?\?>|<!--[\s\S]*?-->|<\?(?!xml)[\s\S]*?\?>|<!DOCTYPE[\s\S]*?>)\s*)*)",
    re.DOTALL,
)


_TRANSLATABLE_TAGS = {
    "title",
    "shortdesc",
    "context",
    "info",
    "note",
    "postreq",
    "section",
    "result",
    "p",
    "li",
    "entry",
    "choice",
    "ph",
    "cmd",
    "stepxmp",
    "stepresult",
    "xref",
}
_NON_TRANSLATABLE_TAGS = {
    "codeblock",
    "codeph",
    "filepath",
    "pre",
    "lines",
    "screen",
    "msgblock",
    "userinput",
    "systemoutput",
}


@dataclass(slots=True)
class DitaTextTarget:
    """Single mutable text slot inside a DITA XML tree."""

    element_path: tuple[int, ...]
    field_name: str
    tag_name: str


@dataclass(slots=True)
class DitaPreparedDocument(PreparedDocument):
    """Prepared DITA document carrying source text and target locations."""

    source_text: str = ""
    leading_xml_text: str = ""
    text_targets: list[DitaTextTarget] = field(default_factory=list)
    document_type: str = DITA_DOCUMENT_TYPE


@dataclass(slots=True)
class DitaProtectedPlaceholder:
    """Protected raw content replaced by a stable placeholder token."""

    token: str
    raw_text: str
    kind: str


class DitaDocumentHandler(DocumentHandler):
    """Minimal DITA handler for extracting and rebuilding text nodes safely."""

    document_type = DITA_DOCUMENT_TYPE

    def __init__(self, *, max_segment_length: int = 500) -> None:
        if max_segment_length <= 0:
            raise ValueError("max_segment_length must be greater than zero.")
        self.max_segment_length = max_segment_length
        self._placeholder_index = 0

    def prepare_document(
        self,
        source_text: str,
        *,
        settings: AppSettings,
    ) -> PreparedDocument:
        del settings
        self._placeholder_index = 0
        root = self._parse_xml_root(source_text)
        leading_xml_text = self._extract_leading_xml_text(source_text)
        blocks: list[PreparedDocumentBlock] = []
        segments: list[DocumentSegment] = []
        text_targets: list[DitaTextTarget] = []

        for target in self._collect_text_targets(root):
            text_value = self._read_target_text(root, target)
            if not text_value.strip():
                continue
            protected_text, placeholders = self._protect_text_literals(text_value)
            chunk_texts = self._split_text(protected_text)
            block_index = len(blocks)
            segment_ids: list[str] = []

            blocks.append(
                PreparedDocumentBlock(
                    block_index=block_index,
                    block_type=target.tag_name,
                    protected_text=protected_text,
                    placeholders=placeholders,
                    segment_ids=segment_ids,
                    translatable=True,
                    meta={
                        "xml_tag": target.tag_name,
                        "xml_field": target.field_name,
                    },
                )
            )

            for order_in_block, chunk_text in enumerate(chunk_texts):
                segment_id = f"dita_seg_{len(segments):04d}"
                segments.append(
                    DocumentSegment(
                        id=segment_id,
                        block_index=block_index,
                        block_type=target.tag_name,
                        order_in_block=order_in_block,
                        text=chunk_text,
                    )
                )
                segment_ids.append(segment_id)
            text_targets.append(target)

        return DitaPreparedDocument(
            blocks=blocks,
            segments=segments,
            trailing_newline=source_text.endswith("\n"),
            source_text=source_text,
            leading_xml_text=leading_xml_text,
            text_targets=text_targets,
        )

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
        if not isinstance(document, DitaPreparedDocument):
            raise TypeError("DITA rebuild requires a DitaPreparedDocument instance.")

        root = self._parse_xml_root(document.source_text)
        rebuilt_blocks = self.rebuild_protected_block_texts(
            document,
            translated_segment_texts,
        )

        for block, target, rebuilt_text in zip(
            document.blocks,
            document.text_targets,
            rebuilt_blocks,
            strict=True,
        ):
            element = self._resolve_element(root, target.element_path)
            restored_text = self._restore_text(rebuilt_text, block.placeholders)
            if target.field_name == "text":
                element.text = restored_text
            else:
                element.tail = restored_text

        restored = ET.tostring(root, encoding="unicode")
        if document.leading_xml_text:
            restored = f"{document.leading_xml_text}{restored}"
        if document.trailing_newline:
            restored += "\n"
        return restored

    def output_extension(self, source_path: str | Path) -> str:
        suffix = Path(source_path).suffix.lower()
        return suffix or ".dita"

    def extract_language_detection_text(self, source_text: str) -> str:
        try:
            root = self._parse_xml_root(source_text)
        except DocumentParseError:
            return source_text

        text_samples: list[str] = []
        for target in self._collect_text_targets(root):
            text_value = self._read_target_text(root, target).strip()
            if text_value:
                text_samples.append(text_value)

        return "\n".join(text_samples) if text_samples else source_text

    def _collect_text_targets(
        self,
        root: ET.Element,
    ) -> Iterable[DitaTextTarget]:
        yield from self._walk_element(
            root,
            current_path=(),
            under_translatable_parent=False,
            blocked=False,
        )

    def _walk_element(
        self,
        element: ET.Element,
        *,
        current_path: tuple[int, ...],
        under_translatable_parent: bool,
        blocked: bool,
    ) -> Iterable[DitaTextTarget]:
        tag_name = self._local_name(element.tag)
        blocked_here = blocked or tag_name in _NON_TRANSLATABLE_TAGS
        if element.attrib.get("translate", "").lower() == "no":
            blocked_here = True

        is_translatable = tag_name in _TRANSLATABLE_TAGS
        if is_translatable and not blocked_here and (element.text or "").strip():
            yield DitaTextTarget(
                element_path=current_path,
                field_name="text",
                tag_name=tag_name,
            )

        for child_index, child in enumerate(list(element)):
            child_path = current_path + (child_index,)
            yield from self._walk_element(
                child,
                current_path=child_path,
                under_translatable_parent=under_translatable_parent or is_translatable,
                blocked=blocked_here,
            )
            if (
                (under_translatable_parent or is_translatable)
                and not blocked_here
                and (child.tail or "").strip()
            ):
                yield DitaTextTarget(
                    element_path=child_path,
                    field_name="tail",
                    tag_name=tag_name,
                )

    def _read_target_text(self, root: ET.Element, target: DitaTextTarget) -> str:
        element = self._resolve_element(root, target.element_path)
        return element.text if target.field_name == "text" else (element.tail or "")

    def _resolve_element(self, root: ET.Element, path: tuple[int, ...]) -> ET.Element:
        element = root
        for child_index in path:
            element = list(element)[child_index]
        return element

    def _local_name(self, tag: object) -> str:
        if not isinstance(tag, str):
            return ""
        if "}" in tag:
            return tag.rsplit("}", 1)[-1]
        return tag

    def _parse_xml_root(self, source_text: str) -> ET.Element:
        parser = ET.XMLParser(
            target=ET.TreeBuilder(insert_comments=True, insert_pis=True)
        )
        try:
            return ET.fromstring(source_text, parser=parser)
        except ET.ParseError as exc:
            raise DocumentParseError(f"DITA XML 解析失败：{exc}") from exc

    def _extract_leading_xml_text(self, source_text: str) -> str:
        match = _LEADING_XML_MISC_RE.match(source_text)
        if match is None:
            return ""
        return match.group("prefix")

    def _split_text(self, text: str) -> list[str]:
        if len(text) <= self.max_segment_length:
            return [text] if text else []

        sentence_chunks = self._split_by_sentence(text)
        sentence_segments = self._pack_chunks(sentence_chunks)
        if self._all_within_limit(sentence_segments):
            return sentence_segments

        newline_chunks = self._split_by_newline(text)
        newline_segments = self._pack_chunks(newline_chunks)
        if self._all_within_limit(newline_segments):
            return newline_segments

        return self._hard_split(text)

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

    def _protect_text_literals(
        self,
        text: str,
    ) -> tuple[str, list[DitaProtectedPlaceholder]]:
        protected_text = text
        placeholders: list[DitaProtectedPlaceholder] = []

        for pattern, kind in (
            (_URL_LIKE_RE, "url_literal"),
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
    ) -> tuple[str, list[DitaProtectedPlaceholder]]:
        placeholders: list[DitaProtectedPlaceholder] = []
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

    def _restore_text(
        self,
        text: str,
        placeholders: list[DitaProtectedPlaceholder],
    ) -> str:
        restored = text
        for placeholder in placeholders:
            restored = restored.replace(placeholder.token, placeholder.raw_text)
        return restored

    def _is_inside_placeholder_token(self, text: str, start: int, end: int) -> bool:
        return (
            start >= 2
            and end + 2 <= len(text)
            and text[start - 2 : start] == "@@"
            and text[end : end + 2] == "@@"
        )

    def _create_placeholder(self, raw_text: str, kind: str) -> DitaProtectedPlaceholder:
        token = f"@@PROTECT_{self._placeholder_index:04d}@@"
        self._placeholder_index += 1
        return DitaProtectedPlaceholder(token=token, raw_text=raw_text, kind=kind)
