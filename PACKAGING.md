# Desktop Packaging

## Purpose

This document describes how to build and verify the desktop packages for Windows and macOS.

## Build Command

Run from the project root:

Windows:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

macOS:

```bash
bash ./scripts/build_macos.sh
```

Default behavior:

- The packaged `.env` is copied from `.env.example`
- This avoids shipping a real API key by accident

If you intentionally need an internal build that includes the real local `.env`, run:

```powershell
$env:DOC_TRANS_PACKAGE_REAL_ENV=1
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

## Build Output

Folder release:

```text
dist\DocTranslationTool\
```

Main executable:

```text
dist\DocTranslationTool\DocTranslationTool.exe
```

Zip release:

```text
dist\DocTranslationTool-v<version>-win64.zip
```

macOS folder release:

```text
dist-macos/DocTranslationTool-macos-<arch>/
```

macOS app bundle:

```text
dist-macos/DocTranslationTool-macos-<arch>/DocTranslationTool.app
```

macOS zip release:

```text
dist-macos/DocTranslationTool-v<version>-macos-<arch>.zip
```

## Files Expected In Release Folder

Windows required runtime files:

- `DocTranslationTool.exe`
- `_internal\`
- `.env`

macOS required runtime files:

- `DocTranslationTool.app`
- `.env`

Recommended companion files:

- `README.md`
- `使用指南.md`
- `CHANGELOG.md`
- `PACKAGING.md`
- `.env.example`
- `settings.example.json`
- `glossary.example.json`

## Runtime Config Rules

Windows packaged app:

- Reads runtime config from the same directory as `DocTranslationTool.exe`

macOS packaged app:

- Reads runtime config from the same directory that contains `DocTranslationTool.app`
- This keeps `.env`, `settings.json`, and `glossary.json` outside the `.app` bundle so end users do not need to edit files inside `Contents/`

Supported runtime files:

- `.env`
- `settings.json`
- `glossary.json`

Priority:

1. Runtime environment variables
2. `.env`
3. `settings.json`
4. Code defaults

End-user configuration path:

- Most users can configure the packaged app from the GUI `模型配置` dialog after launch
- `glossary.json` can also be maintained from the GUI `术语配置` dialog
- Keep `.env.example`, `settings.example.json`, and `glossary.example.json` next to the packaged app as editable templates / references

## Release Checklist

Before publishing a package, check these items:

1. The packaged app can launch normally on the target platform
2. On Windows, `DocTranslationTool.exe` file properties show the expected `File version` / `Product version`
3. `.env` is the intended release config
4. `使用指南.md` is present
5. `CHANGELOG.md` is present
6. `.env.example`, `settings.example.json`, and `glossary.example.json` are present if the package is meant for handoff to other users
7. The release folder does not contain test output or demo output
8. The zip can be extracted and run as a full folder

## Notes

- Do not send the Windows `exe` alone.
- Do not send the macOS `.app` alone if the release expects companion config and docs next to it.
- Send either the whole packaged folder or the zip for the target platform.
- If the package is for internal company use, real internal API config may be kept in `.env` if that matches your release policy.
- If the package is for wider distribution, replace sensitive config before shipping.
