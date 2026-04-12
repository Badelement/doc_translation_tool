# 文档索引

本目录中的文档以 `source/` 作为项目工作目录来组织。

## 用户文档

### 快速开始
- **[README.md](README.md)** - 项目介绍和快速开始指南
- **[QUICK_START.md](QUICK_START.md)** - 当前工作区的最小操作路径
- **[使用指南.md](使用指南.md)** - 详细的中文使用指南

### 配置说明
- **[settings参数说明.md](settings参数说明.md)** - settings.json 配置参数详细说明

### 打包部署
- **[PACKAGING.md](PACKAGING.md)** - Windows 打包说明
- **[PACKAGING_MACOS.md](PACKAGING_MACOS.md)** - macOS 打包说明

## 开发文档

### 项目协作
- **[CLAUDE.md](CLAUDE.md)** - Claude Code 协作指南，包含项目架构和开发规范

### 变更记录
- **[CHANGELOG.md](CHANGELOG.md)** - 版本变更历史记录

### 重构文档
- **[REFACTORING_SUMMARY.md](REFACTORING_SUMMARY.md)** - 代码重构总结（已完成的工作）
- **[REFACTORING_PLAN.md](REFACTORING_PLAN.md)** - 代码重构计划（完整的 4 阶段计划）

## 文档说明

### 用户应该阅读的文档
1. 首次使用：`README.md` → `使用指南.md`
2. 配置调整：`settings参数说明.md`
3. 打包部署：`PACKAGING.md` 或 `PACKAGING_MACOS.md`

### 开发者应该阅读的文档
1. 项目架构：`CLAUDE.md`
2. 重构历史：`REFACTORING_SUMMARY.md`
3. 未来计划：`REFACTORING_PLAN.md`
4. 变更记录：`CHANGELOG.md`

## 项目结构

```text
workspace/
├── README.md
├── source/
│   ├── doc_translation_tool/
│   ├── tests/
│   ├── scripts/
│   ├── docs/
│   └── *.md
└── releases/
```

## 说明

- `source/` 是你日常工作的目录
- `releases/` 只放打包产物
- 根目录 `README.md` 只负责导航，不再重复项目细节
