from __future__ import annotations

import sys
from pathlib import Path

from doc_translation_tool import __version__


def _resolve_frozen_runtime_project_root(executable_path: str | Path) -> Path:
    executable = Path(executable_path).resolve()

    # For macOS app bundles, keep runtime config next to the .app so end users
    # do not need to edit files inside Contents/.
    if (
        executable.parent.name == "MacOS"
        and executable.parent.parent.name == "Contents"
        and executable.parent.parent.parent.suffix == ".app"
    ):
        return executable.parent.parent.parent.parent

    return executable.parent


def resolve_runtime_project_root() -> Path:
    if getattr(sys, "frozen", False):
        return _resolve_frozen_runtime_project_root(sys.executable)

    return Path(__file__).resolve().parent.parent


def describe_layout() -> str:
    project_root = resolve_runtime_project_root()
    return "\n".join(
        [
            "Document Translation Tool",
            f"Version: {__version__}",
            f"Project root: {project_root}",
            "Status: GUI translation pipeline ready",
            "Next task: package desktop delivery build",
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
