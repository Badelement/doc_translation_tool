# Workspace Layout

This workspace is split into two top-level directories:

- `source/`: source code, tests, scripts, docs, and packaging config
- `releases/`: generated app bundles and archives

Common entry points:

```bash
cd source
python3 app.py
```

```bash
cd source
uv run --extra dev python -m pytest
```

```bash
cd source
bash scripts/build_macos.sh
```

```powershell
cd source
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

Build outputs:

- macOS: `releases/macos/`
- Windows: `releases/windows/`
