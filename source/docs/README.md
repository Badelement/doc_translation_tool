# Project Docs

This directory stores auxiliary project documentation inside the `source/` project root.

## Layout

- `assets/screenshots/`: local screenshots and image scraps used during development review
- `notes/`: internal development notes and issue logs
- `superpowers/plans/`: local planning notes created during repo maintenance work

## High-Signal Docs In `source/`

The main user-facing and developer-facing docs live directly under `source/`:

- `README.md`
- `PACKAGING.md`
- `PACKAGING_MACOS.md`
- `使用指南.md`
- `settings参数说明.md`
- `CHANGELOG.md`
- `CLAUDE.md`

## Cleanup

To remove common local cache and test output directories, run:

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\clean_workspace.ps1
```
