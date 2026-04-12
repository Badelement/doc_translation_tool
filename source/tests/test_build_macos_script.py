from __future__ import annotations

import os
import shutil
import stat
import subprocess
from pathlib import Path


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_build_macos_release_does_not_include_outer_onedir_runtime(
    tmp_path: Path,
) -> None:
    repo_root = Path(__file__).resolve().parents[1]
    workspace_root = tmp_path / "workspace"
    project_root = workspace_root / "source"
    scripts_dir = project_root / "scripts"

    scripts_dir.mkdir(parents=True)
    shutil.copy2(repo_root / "scripts" / "build_macos.sh", scripts_dir / "build_macos.sh")

    (project_root / "app.py").write_text("print('stub app')\n", encoding="utf-8")
    (project_root / "README.md").write_text("# Test Package\n", encoding="utf-8")
    (project_root / "settings.example.json").write_text("{}\n", encoding="utf-8")
    (project_root / ".env.example").write_text("API_KEY=\n", encoding="utf-8")

    fake_python = tmp_path / "fake_python.sh"
    _write_executable(
        fake_python,
        """#!/bin/bash
set -e
DISTPATH=""
NAME=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --distpath)
      DISTPATH="$2"
      shift 2
      ;;
    --name)
      NAME="$2"
      shift 2
      ;;
    *)
      shift 1
      ;;
  esac
done

mkdir -p "$DISTPATH/$NAME/_internal"
printf 'outer-runtime\\n' > "$DISTPATH/$NAME/$NAME"
printf 'dup-runtime\\n' > "$DISTPATH/$NAME/_internal/runtime.txt"

APP_ROOT="$DISTPATH/$NAME.app/Contents/MacOS"
mkdir -p "$APP_ROOT/PySide6/translations"
mkdir -p "$APP_ROOT/PySide6/Qt/plugins/platforms"
mkdir -p "$APP_ROOT/PySide6/Qt/plugins/imageformats"
mkdir -p "$APP_ROOT/PySide6/Qt/plugins/generic"
printf 'app-binary\\n' > "$APP_ROOT/$NAME"
printf 'keep\\n' > "$APP_ROOT/PySide6/translations/qt_en.qm"
printf 'keep\\n' > "$APP_ROOT/PySide6/translations/qt_zh_CN.qm"
printf 'drop\\n' > "$APP_ROOT/PySide6/translations/qt_de.qm"
printf 'drop\\n' > "$APP_ROOT/PySide6/Qt/plugins/platforms/libqminimal.dylib"
printf 'keep\\n' > "$APP_ROOT/PySide6/Qt/plugins/platforms/libqcocoa.dylib"
printf 'drop\\n' > "$APP_ROOT/PySide6/Qt/plugins/imageformats/libqpdf.dylib"
printf 'drop\\n' > "$APP_ROOT/PySide6/Qt/plugins/generic/plugin.dylib"
""",
    )

    build_script = scripts_dir / "build_macos.sh"
    result = subprocess.run(
        ["bash", str(build_script)],
        cwd=project_root,
        env={**os.environ, "PYTHON": str(fake_python)},
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr or result.stdout

    release_dir = workspace_root / "releases" / "macos" / "DocTranslationTool"
    assert release_dir.is_dir()
    assert (release_dir / "DocTranslationTool.app").is_dir()
    assert (release_dir / ".env").is_file()
    assert (release_dir / "README.md").is_file()
    assert (release_dir / "settings.example.json").is_file()

    assert not (release_dir / "DocTranslationTool").exists()
    assert not (release_dir / "_internal").exists()

    translations_dir = (
        release_dir
        / "DocTranslationTool.app"
        / "Contents"
        / "MacOS"
        / "PySide6"
        / "translations"
    )
    assert (translations_dir / "qt_en.qm").is_file()
    assert (translations_dir / "qt_zh_CN.qm").is_file()
    assert not (translations_dir / "qt_de.qm").exists()

    plugins_dir = (
        release_dir
        / "DocTranslationTool.app"
        / "Contents"
        / "MacOS"
        / "PySide6"
        / "Qt"
        / "plugins"
    )
    assert (plugins_dir / "platforms" / "libqcocoa.dylib").is_file()
    assert not (plugins_dir / "platforms" / "libqminimal.dylib").exists()
    assert not (plugins_dir / "imageformats" / "libqpdf.dylib").exists()
    assert not (plugins_dir / "generic").exists()

    assert (workspace_root / "releases" / "macos" / "DocTranslationTool-macos.zip").is_file()
