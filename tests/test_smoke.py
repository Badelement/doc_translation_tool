from pathlib import Path

from doc_translation_tool import __version__
from doc_translation_tool.app import (
    _resolve_frozen_runtime_project_root,
    describe_layout,
    resolve_runtime_project_root,
)


def test_describe_layout_contains_status() -> None:
    summary = describe_layout()
    assert "Document Translation Tool" in summary
    assert f"Version: {__version__}" in summary
    assert "Project root:" in summary
    assert "Status:" in summary
    assert "Next task:" in summary


def test_resolve_runtime_project_root_uses_source_project_root() -> None:
    root = resolve_runtime_project_root()

    assert (root / "pyproject.toml").exists()


def test_resolve_runtime_project_root_uses_executable_directory_when_frozen(
    monkeypatch,
    tmp_path: Path,
) -> None:
    fake_executable = tmp_path / "DocTranslationTool.exe"
    fake_executable.write_text("", encoding="utf-8")

    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(fake_executable))

    assert resolve_runtime_project_root() == tmp_path


def test_resolve_frozen_runtime_project_root_uses_parent_of_app_bundle_on_macos(
    tmp_path: Path,
) -> None:
    executable = (
        tmp_path
        / "release"
        / "DocTranslationTool.app"
        / "Contents"
        / "MacOS"
        / "DocTranslationTool"
    )
    executable.parent.mkdir(parents=True)
    executable.write_text("", encoding="utf-8")

    assert _resolve_frozen_runtime_project_root(executable) == tmp_path / "release"
