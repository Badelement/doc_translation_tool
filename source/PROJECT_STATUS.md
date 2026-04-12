# 项目状态报告

## 当前状态

这个工作区已经整理为两层结构：

- 根目录：工作区导航与发布产物入口
- `source/`：源码、测试、脚本、配置和项目文档
- `../releases/`：构建产物输出目录

## 项目概况

文档翻译工具支持 Markdown 和 DITA 文档的中英互译，使用 PySide6 构建桌面 GUI，并提供单文件与目录批量两种工作模式。

## 当前重点

- 保持 `source/` 作为唯一的源码工作目录
- 保持 `../releases/` 作为唯一的打包输出目录
- 避免把虚拟环境、构建目录和缓存重新混入源码树

## 当前结构

```text
workspace/
├── README.md
├── .gitignore
├── source/
│   ├── app.py
│   ├── pyproject.toml
│   ├── doc_translation_tool/
│   ├── tests/
│   ├── scripts/
│   ├── docs/
│   ├── README.md
│   ├── CLAUDE.md
│   ├── PACKAGING.md
│   ├── PACKAGING_MACOS.md
│   └── 使用指南.md
└── releases/
    └── README.md
```

## 日常命令

从 `source/` 目录运行：

```bash
python3 app.py
```

```bash
uv run --extra dev python -m pytest
```

```bash
bash scripts/build_macos.sh
```

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

## 发布产物位置

- macOS: `../releases/macos/`
- Windows: `../releases/windows/`

## 文档导航

- 用户入口：`README.md`
- 详细使用：`使用指南.md`
- 打包说明：`PACKAGING.md`、`PACKAGING_MACOS.md`
- 协作说明：`CLAUDE.md`
- 文档索引：`DOCS_INDEX.md`

## 维护原则

- 不在 `source/` 内保留发布产物
- 不在工作区内长期保留 `.venv`、`dist_stage`、测试缓存
- 过时的状态快照应改写为稳定说明，而不是继续堆叠历史数字
