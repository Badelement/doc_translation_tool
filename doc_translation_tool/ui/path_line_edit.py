from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from PySide6.QtCore import QMimeData
from PySide6.QtGui import QDragEnterEvent, QDropEvent
from PySide6.QtWidgets import QLineEdit, QWidget


class PathLineEdit(QLineEdit):
    """QLineEdit that accepts local file-system drag and drop."""

    def __init__(
        self,
        *,
        path_kind: str,
        on_path_received: Callable[[str], None],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.path_kind = path_kind
        self.on_path_received = on_path_received
        self.setAcceptDrops(True)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:
        if self.extract_path_from_mime_data(event.mimeData(), self.path_kind):
            event.acceptProposedAction()
            return
        super().dragEnterEvent(event)

    def dropEvent(self, event: QDropEvent) -> None:
        dropped_path = self.extract_path_from_mime_data(event.mimeData(), self.path_kind)
        if dropped_path is None:
            super().dropEvent(event)
            return

        self.setText(dropped_path)
        self.on_path_received(dropped_path)
        event.acceptProposedAction()

    @staticmethod
    def extract_path_from_mime_data(
        mime_data: QMimeData,
        path_kind: str,
    ) -> str | None:
        if not mime_data.hasUrls():
            return None

        for url in mime_data.urls():
            if not url.isLocalFile():
                continue

            candidate = Path(url.toLocalFile()).expanduser()
            if PathLineEdit._matches_path_kind(candidate, path_kind):
                return str(candidate)

        return None

    @staticmethod
    def _matches_path_kind(path: Path, path_kind: str) -> bool:
        if path_kind == "markdown_file":
            return path.is_file() and path.suffix.lower() == ".md"
        if path_kind == "directory":
            return path.is_dir()
        raise ValueError(f"Unsupported path kind: {path_kind}")
