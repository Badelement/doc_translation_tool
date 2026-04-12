# Windows Packaging

## Purpose

This document describes how to build and verify the Windows package.

## Build Command

Run from the `source/` directory:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

## Build Output

Folder release:

```text
..\releases\windows\DocTranslationTool\
```

Main executable:

```text
..\releases\windows\DocTranslationTool\DocTranslationTool.exe
```

Zip release:

```text
..\releases\windows\DocTranslationTool-win64.zip
```

The zip is created from the contents of `..\releases\windows\DocTranslationTool\`.
After extraction, users should land directly in the runtime folder that contains `DocTranslationTool.exe`, `_internal\`, and `.env`.
The zip does not add another `..\releases\windows\DocTranslationTool\` directory layer.

## Files Expected In Release Folder

Required runtime files:

- `DocTranslationTool.exe`
- `_internal\`
- `.env`

Recommended companion files:

- `README.md`
- `使用指南.md`
- `settings参数说明.md`
- `CHANGELOG.md`
- `PACKAGING.md`
- `settings.example.json`
- `glossary.example.json`

## Runtime Config Rules

The packaged app reads runtime config from the same directory as the exe.

Supported runtime files next to `DocTranslationTool.exe`:

- `.env`
- `settings.json`
- `glossary.json`

Priority:

1. Runtime environment variables
2. `.env`
3. `settings.json`
4. Code defaults

## Release Checklist

Before publishing a package, check these items:

1. `DocTranslationTool.exe` can launch normally
2. `.env` is the intended release config
3. `使用指南.md` is present
4. `CHANGELOG.md` is present
5. The release folder does not contain test output or demo output
6. The zip can be extracted and run as a full folder

## Notes

- Do not send the `exe` alone.
- Send either the whole `..\releases\windows\DocTranslationTool\` folder or the zip.
- If the package is for internal company use, real internal API config may be kept in `.env` if that matches your release policy.
- If the package is for wider distribution, replace sensitive config before shipping.
