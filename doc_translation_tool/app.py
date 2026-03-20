from __future__ import annotations

import sys
from pathlib import Path

from doc_translation_tool import __version__


def resolve_runtime_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent

    return Path(__file__).resolve().parent.parent


def describe_layout() -> str:
    project_root = resolve_runtime_project_root()
    return "\n".join(
        [
            "Document Translation Tool",
            f"Version: {__version__}",
            f"Project root: {project_root}",
            "Status: GUI translation pipeline ready",
            "Next task: package Windows delivery build",
        ]
    )


def main() -> int:
    try:
        from PySide6.QtWidgets import QApplication
    except ModuleNotFoundError:
        print("PySide6 is not installed.")
        print(describe_layout())
        print("Install project dependencies before launching the desktop UI.")
        return 1

    from doc_translation_tool.ui.main_window import MainWindow

    app = QApplication(sys.argv)
    window = MainWindow(project_root=resolve_runtime_project_root())
    window.show()
    return app.exec()
