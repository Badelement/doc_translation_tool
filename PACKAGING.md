# Windows Packaging

## Purpose

This document describes how to build and verify the Windows package.

## Build Command

Run from the project root:

```powershell
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
dist\DocTranslationTool-win64.zip
```

## Files Expected In Release Folder

Required runtime files:

- `DocTranslationTool.exe`
- `_internal\`
- `.env`

Recommended companion files:

- `README.md`
- `使用指南.md`
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
- Send either the whole `dist\DocTranslationTool\` folder or the zip.
- If the package is for internal company use, real internal API config may be kept in `.env` if that matches your release policy.
- If the package is for wider distribution, replace sensitive config before shipping.
