#!/bin/bash

set -euo pipefail

project_root="$(cd "$(dirname "$0")/.." && pwd)"
dist_root="$project_root/dist-macos"
staging_dist_root="$project_root/dist-macos-stage"
build_root="$project_root/build-macos"
release_name="DocTranslationTool"
package_real_env="${DOC_TRANS_PACKAGE_REAL_ENV:-0}"

if [[ -x "$project_root/.venv/bin/python" ]]; then
  python_bin="$project_root/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  python_bin="$(command -v python3)"
elif command -v python >/dev/null 2>&1; then
  python_bin="$(command -v python)"
else
  echo "[build] Python interpreter not found. Activate the project environment first." >&2
  exit 1
fi

version="$("$python_bin" -c 'from doc_translation_tool import __version__; print(__version__)')"

if [[ -z "$version" ]]; then
  echo "[build] Failed to resolve package version." >&2
  exit 1
fi

arch="$(uname -m)"
version_label="v$version"
release_dir_name="${release_name}-macos-${arch}"
staging_release_dir="$staging_dist_root/$release_dir_name"
release_dir="$dist_root/$release_dir_name"
archive_path="$dist_root/${release_name}-${version_label}-macos-${arch}.zip"

template_files=(
  "settings.example.json"
  "glossary.example.json"
  "CHANGELOG.md"
  "README.md"
  "PACKAGING.md"
)

echo "[build] Project root: $project_root"
echo "[build] Python interpreter: $python_bin"
echo "[build] Package version: $version"
echo "[build] Target architecture: $arch"
echo "[build] Package real .env: $package_real_env"

rm -rf "$staging_dist_root"
rm -rf "$build_root"
rm -rf "$release_dir"
rm -f "$archive_path"

mkdir -p "$build_root"
mkdir -p "$staging_release_dir"
mkdir -p "$dist_root"

"$python_bin" -m PyInstaller \
  --noconfirm \
  --clean \
  --windowed \
  --name "$release_name" \
  --distpath "$staging_dist_root" \
  --workpath "$build_root" \
  --specpath "$build_root" \
  --hidden-import PySide6.QtCore \
  --hidden-import PySide6.QtGui \
  --hidden-import PySide6.QtWidgets \
  app.py

app_bundle="$staging_dist_root/${release_name}.app"
if [[ ! -d "$app_bundle" ]]; then
  echo "[build] Expected app bundle not found: $app_bundle" >&2
  exit 1
fi

cp -R "$app_bundle" "$staging_release_dir/"
echo "[build] Copied app bundle"

runtime_env_source="$project_root/.env.example"
if [[ "$package_real_env" == "1" ]]; then
  runtime_env_source="$project_root/.env"
fi
if [[ ! -f "$runtime_env_source" ]]; then
  echo "[build] Runtime env source not found: $runtime_env_source" >&2
  exit 1
fi

cp "$runtime_env_source" "$staging_release_dir/.env"
echo "[build] Copied runtime env template from: $runtime_env_source"

for file_name in "${template_files[@]}"; do
  source_path="$project_root/$file_name"
  if [[ -f "$source_path" ]]; then
    cp "$source_path" "$staging_release_dir/$file_name"
    echo "[build] Copied $file_name"
  fi
done

guide_source="$project_root/使用指南.md"
if [[ -f "$guide_source" ]]; then
  cp "$guide_source" "$staging_release_dir/使用指南.md"
  echo "[build] Copied user guide"
fi

cp -R "$staging_release_dir" "$release_dir"
echo "[build] Synced staged release into dist-macos"

(
  cd "$dist_root"
  ditto -c -k --sequesterRsrc --keepParent "$release_dir_name" "$(basename "$archive_path")"
)
echo "[build] Created release archive: $archive_path"

rm -rf "$staging_dist_root"
echo "[build] Removed staging dist directory"
echo "[build] Build completed: $release_dir"
