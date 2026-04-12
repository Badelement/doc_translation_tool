"""Text processing utilities with performance optimizations."""

from __future__ import annotations

import re
from typing import Final

# Common file extensions for fast lookup (avoiding regex backtracking)
# Used by both DITA and Markdown handlers
KNOWN_FILE_EXTENSIONS: Final[frozenset[str]] = frozenset({
    "dts", "dtbo", "cfg", "conf", "ini", "yaml", "yml", "toml", "mk", "ko",
    "sh", "xml", "json", "html", "pdf", "h", "c", "cc", "cpp", "hpp",
    "py", "txt", "bin", "img", "rc", "dll", "so", "log", "csv", "md", "dita",
})

# Pre-compiled regex patterns for common operations
# These are compiled once at module load time for better performance

# URL pattern - simplified to avoid catastrophic backtracking
URL_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"https?://[^\s<>\"']{1,2048}",
    re.IGNORECASE
)

# Uppercase constant pattern (e.g., CONFIG_VALUE)
UPPER_CONSTANT_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+\b"
)

# Path-like pattern - Windows and Unix paths
# Optimized to reduce backtracking
PATH_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![@\w])"
    r"(?:"
    r"[A-Za-z]:\\[^\s<>\"'|]*"  # Windows absolute path
    r"|"
    r"(?:\.\.?|~)?[/\\][^\s<>\"'|]*"  # Unix/relative path
    r")"
)

# HTML/XML tag pattern - simplified
HTML_TAG_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"</?[A-Za-z][A-Za-z0-9:_-]*(?:\s+[^<>\n]*?)?\s*/?>"
)

_FILE_REFERENCE_EXTENSIONS: Final[str] = "|".join(
    sorted(KNOWN_FILE_EXTENSIONS, key=len, reverse=True)
)
FILE_REFERENCE_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![@A-Za-z0-9_])"
    r"(?:[A-Za-z]:\\)?"
    r"(?:\.\.?[/\\]|~[/\\]|[/\\])?"
    r"[A-Za-z0-9_{}-]+(?:[./\\][A-Za-z0-9_{}-]+)*"
    rf"\.(?:{_FILE_REFERENCE_EXTENSIONS})"
    r"(?![A-Za-z0-9_])",
    re.IGNORECASE,
)


def looks_like_file_reference(text: str) -> bool:
    """Fast check if text looks like a file reference without regex.

    This is a performance-optimized alternative to regex matching for
    file-like patterns. It checks if the text ends with a known extension.

    Args:
        text: The text to check

    Returns:
        True if the text appears to be a file reference
    """
    if not text or len(text) < 3:
        return False

    # Find the last dot
    try:
        dot_index = text.rindex(".")
    except ValueError:
        return False

    # Get extension (handle cases like "file.tar.gz")
    extension = text[dot_index + 1:].lower()

    # Check if it's a known extension
    return extension in KNOWN_FILE_EXTENSIONS


def extract_file_references(text: str) -> list[tuple[int, int, str]]:
    """Extract file references from text with their positions.

    This is a safer alternative to regex finditer for file matching.
    Returns list of (start, end, matched_text) tuples.

    Args:
        text: The text to search

    Returns:
        List of (start, end, matched_text) tuples
    """
    results: list[tuple[int, int, str]] = []
    for match in FILE_REFERENCE_PATTERN.finditer(text):
        candidate = match.group(0)
        if looks_like_file_reference(candidate):
            results.append((match.start(), match.end(), candidate))

    return results


def split_text_into_sentences(text: str) -> list[str]:
    """Split text into sentences without regex.

    This is a performance-optimized sentence splitter that handles
    both English and Chinese punctuation.

    Args:
        text: The text to split

    Returns:
        List of sentence strings
    """
    if not text:
        return []

    sentences: list[str] = []
    current: list[str] = []

    # Sentence-ending punctuation
    sentence_enders = frozenset(".!?。！？")

    for i, char in enumerate(text):
        current.append(char)

        if char in sentence_enders:
            # Check if this is really a sentence boundary
            next_char = text[i + 1] if i + 1 < len(text) else ""
            if next_char == "" or next_char.isspace() or next_char in "\"')]}>":
                sentence = "".join(current).strip()
                if sentence:
                    sentences.append(sentence)
                current = []

    # Add remaining text
    if current:
        remaining = "".join(current).strip()
        if remaining:
            sentences.append(remaining)

    return sentences


def truncate_text(text: str, max_length: int, suffix: str = "...") -> str:
    """Truncate text to maximum length.

    Args:
        text: The text to truncate
        max_length: Maximum allowed length
        suffix: Suffix to add if truncated

    Returns:
        Truncated text
    """
    if len(text) <= max_length:
        return text
    return text[: max_length - len(suffix)] + suffix
