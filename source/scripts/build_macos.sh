#!/bin/bash
set -e

# Get project root (parent of scripts directory)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WORKSPACE_ROOT="$(dirname "$PROJECT_ROOT")"
DIST_ROOT="$WORKSPACE_ROOT/releases"
STAGING_DIST_ROOT="$PROJECT_ROOT/dist_stage"
PYINSTALLER_DIST_ROOT="$STAGING_DIST_ROOT/pyinstaller"
PACKAGE_STAGING_ROOT="$STAGING_DIST_ROOT/package"
BUILD_ROOT="$PROJECT_ROOT/build"
RELEASE_NAME="DocTranslationTool"
MACOS_DIST_DIR="$DIST_ROOT/macos"
RELEASE_DIR="$MACOS_DIST_DIR/$RELEASE_NAME"
STAGING_RELEASE_DIR="$PACKAGE_STAGING_ROOT/$RELEASE_NAME"
APP_NAME="DocTranslationTool.app"
PYINSTALLER_ONEDIR_DIR="$PYINSTALLER_DIST_ROOT/$RELEASE_NAME"
STAGING_APP_PATH="$PYINSTALLER_DIST_ROOT/$APP_NAME"
ZIP_PATH="$MACOS_DIST_DIR/$RELEASE_NAME-macos.zip"
CLEAN_SCRIPT="$SCRIPT_DIR/clean_workspace.sh"

echo "[build] Project root: $PROJECT_ROOT"
echo "[build] Workspace root: $WORKSPACE_ROOT"

# Run cleanup script if it exists
if [ -f "$CLEAN_SCRIPT" ]; then
    echo "[build] Running workspace cleanup script"
    bash "$CLEAN_SCRIPT"
fi

# Remove staging dist directory
if [ -d "$STAGING_DIST_ROOT" ]; then
    echo "[build] Removing staging dist directory: $STAGING_DIST_ROOT"
    rm -rf "$STAGING_DIST_ROOT"
fi

# Remove existing build directory
if [ -d "$BUILD_ROOT" ]; then
    echo "[build] Removing existing build directory: $BUILD_ROOT"
    rm -rf "$BUILD_ROOT"
fi

# Remove existing release archive
if [ -f "$ZIP_PATH" ]; then
    echo "[build] Removing existing release archive: $ZIP_PATH"
    rm -f "$ZIP_PATH"
fi

# Use python3 by default, can be overridden with PYTHON environment variable
PYTHON_PATH="${PYTHON:-python3}"

# Build the app bundle with PyInstaller
cd "$PROJECT_ROOT"
$PYTHON_PATH -m PyInstaller \
    --noconfirm \
    --clean \
    --windowed \
    --name "$RELEASE_NAME" \
    --distpath "$PYINSTALLER_DIST_ROOT" \
    --workpath "$BUILD_ROOT" \
    --specpath "$BUILD_ROOT" \
    --hidden-import PySide6.QtCore \
    --hidden-import PySide6.QtGui \
    --hidden-import PySide6.QtWidgets \
    --osx-bundle-identifier com.internal.doctranslationtool \
    app.py

echo "[build] PyInstaller build completed"

# Create release directory structure
mkdir -p "$STAGING_RELEASE_DIR"

# Move the .app bundle into the release directory
if [ -d "$STAGING_APP_PATH" ]; then
    mv "$STAGING_APP_PATH" "$STAGING_RELEASE_DIR/"
    echo "[build] Moved $APP_NAME to release directory"
else
    echo "[build] ERROR: App bundle not found at $STAGING_APP_PATH"
    exit 1
fi

# Copy template files
TEMPLATE_FILES=(
    "settings.example.json"
    "glossary.example.json"
    "CHANGELOG.md"
    "README.md"
    "PACKAGING.md"
    "使用指南.md"
    "settings参数说明.md"
)

# Copy .env (prefer .env.example if it exists, otherwise use .env)
if [ -f "$PROJECT_ROOT/.env.example" ]; then
    RUNTIME_ENV_SOURCE="$PROJECT_ROOT/.env.example"
elif [ -f "$PROJECT_ROOT/.env" ]; then
    RUNTIME_ENV_SOURCE="$PROJECT_ROOT/.env"
else
    echo "[build] WARNING: No .env or .env.example found"
    RUNTIME_ENV_SOURCE=""
fi

if [ -n "$RUNTIME_ENV_SOURCE" ]; then
    cp "$RUNTIME_ENV_SOURCE" "$STAGING_RELEASE_DIR/.env"
    echo "[build] Copied .env template"
fi

# Copy template and documentation files
for FILE in "${TEMPLATE_FILES[@]}"; do
    if [ -f "$PROJECT_ROOT/$FILE" ]; then
        cp "$PROJECT_ROOT/$FILE" "$STAGING_RELEASE_DIR/"
        echo "[build] Copied $FILE"
    fi
done

# Prune unnecessary Qt translations (keep only English and Chinese)
TRANSLATIONS_DIR="$STAGING_RELEASE_DIR/$APP_NAME/Contents/MacOS/PySide6/translations"
if [ -d "$TRANSLATIONS_DIR" ]; then
    TRANSLATION_KEEP_SET=(
        "qt_en.qm"
        "qt_zh_CN.qm"
        "qtbase_en.qm"
        "qtbase_zh_CN.qm"
    )

    for FILE in "$TRANSLATIONS_DIR"/*.qm; do
        BASENAME=$(basename "$FILE")
        KEEP=false
        for KEEP_FILE in "${TRANSLATION_KEEP_SET[@]}"; do
            if [ "$BASENAME" = "$KEEP_FILE" ]; then
                KEEP=true
                break
            fi
        done

        if [ "$KEEP" = false ]; then
            rm -f "$FILE"
        fi
    done
    echo "[build] Pruned Qt translation files"
fi

# Remove unnecessary Qt plugins
PLUGINS_DIR="$STAGING_RELEASE_DIR/$APP_NAME/Contents/MacOS/PySide6/Qt/plugins"
if [ -d "$PLUGINS_DIR" ]; then
    # Remove entire plugin directories we don't need
    rm -rf "$PLUGINS_DIR/generic" 2>/dev/null || true
    rm -rf "$PLUGINS_DIR/networkinformation" 2>/dev/null || true
    rm -rf "$PLUGINS_DIR/platforminputcontexts" 2>/dev/null || true

    # Remove specific platform plugins we don't need
    rm -f "$PLUGINS_DIR/platforms/libqminimal.dylib" 2>/dev/null || true
    rm -f "$PLUGINS_DIR/platforms/libqoffscreen.dylib" 2>/dev/null || true

    # Remove PDF-related plugins
    rm -f "$PLUGINS_DIR/imageformats/libqpdf.dylib" 2>/dev/null || true

    echo "[build] Removed unused Qt plugins"
fi

# Create final dist directory if it doesn't exist
mkdir -p "$MACOS_DIST_DIR"

# The PyInstaller onedir runtime is only an intermediate build artifact.
if [ -d "$PYINSTALLER_ONEDIR_DIR" ]; then
    echo "[build] Keeping PyInstaller onedir output out of final release: $PYINSTALLER_ONEDIR_DIR"
fi

# Clear existing release directory or create it
if [ -d "$RELEASE_DIR" ]; then
    echo "[build] Clearing existing release directory: $RELEASE_DIR"
    rm -rf "$RELEASE_DIR"
fi
mkdir -p "$RELEASE_DIR"

# Copy staged release to final dist
cp -R "$STAGING_RELEASE_DIR/." "$RELEASE_DIR/"
echo "[build] Synced staged release into dist"

# Create release archive (zip the contents, not the parent directory)
cd "$RELEASE_DIR"
zip -r -q "$ZIP_PATH" .
echo "[build] Created release archive: $ZIP_PATH"

# Remove staging dist directory
cd "$PROJECT_ROOT"
rm -rf "$STAGING_DIST_ROOT"
echo "[build] Removed staging dist directory"

echo "[build] Build completed: $RELEASE_DIR"
echo "[build] Release structure:"
echo "  - $APP_NAME (double-click to launch)"
echo "  - .env (edit API configuration)"
echo "  - Documentation files"
