# 快速开始

## 当前工作区结构

这个工作区已经拆成两部分：

- 根目录：导航入口
- `source/`：源码、测试、脚本、文档
- `releases/`：打包产物

## 进入源码目录

```bash
cd /path/to/workspace/source
```

## 本地运行

```bash
python3 app.py
```

## 运行测试

```bash
uv run --extra dev python -m pytest
```

如果只跑单个测试文件：

```bash
uv run --extra dev python -m pytest tests/test_pipeline.py -v
```

## macOS 打包

```bash
bash scripts/build_macos.sh
```

产物输出到：

```text
../releases/macos/
```

## Windows 打包

```powershell
powershell -ExecutionPolicy Bypass -File .\scripts\build_windows.ps1
```

产物输出到：

```text
..\releases\windows\
```

## 常用文档

- 项目说明：`README.md`
- 使用指南：`使用指南.md`
- Windows 打包：`PACKAGING.md`
- macOS 打包：`PACKAGING_MACOS.md`
- 协作说明：`CLAUDE.md`
