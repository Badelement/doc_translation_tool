# 文档翻译工具

用于翻译单个 Markdown 或 DITA 文档的桌面工具。重点是尽量保留文档结构，并让中英文技术文档的双向翻译更稳一些。

[English](./README.md) | [简体中文](./README.zh-CN.md)

当前发布版本：[v0.4.3](https://github.com/Badelement/doc_translation_tool/releases/tag/v0.4.3)

`v0.4.3` 之后、尚未重新打标签发布的仓库改动，会记录在 [CHANGELOG.md](./CHANGELOG.md) 的 `Unreleased` 小节里。

## 项目简介

这个工具主要解决的是“把一个 Markdown 或 DITA 技术文档稳一点地翻译出来”。

它适合这些场景：

- 一次翻译一个 `.md` 或 `.dita` 文件
- 支持 `中译英` 和 `英译中`
- 尽量保留 Markdown 结构、表格、占位符、front matter，以及 DITA 的 XML 文本节点结构
- 支持 OpenAI 兼容接口和 Anthropic 兼容接口
- 处理大文档时，可以按批次并行翻译
- GUI 会显示配置状态、接口检查状态和批次进度
- GUI 里可以直接维护模型配置和术语表

## 当前已实现

- 单文件 Markdown / DITA 翻译
- 自动识别常见中英文内容并推荐翻译方向
- 可配置的批次大小和并发批次数
- 可以在 GUI 里直接编辑模型配置并写回 `.env`
- 可以在 GUI 里直接编辑 `glossary.json`
- 启动时先检查关键配置是否齐全
- 开始翻译时再检查接口连通性
- 按批次显示进度和完成情况
- 输出新文件，不覆盖原文件

## 快速开始

如果你使用的是 Windows 打包版，最快这样开始：

1. 解压整个 `DocTranslationTool-v版本号-win64.zip`
2. 打开 `dist\DocTranslationTool\`
3. 启动 `DocTranslationTool.exe`
4. 可以直接编辑同目录下的 `.env`，也可以点界面里的“模型配置”
5. 先只填这 3 项：

```env
DOC_TRANS_BASE_URL=你的接口地址
DOC_TRANS_API_KEY=你的API Key
DOC_TRANS_MODEL=你要用的模型名
```

6. 先看左下角“模型状态”
7. 如有术语需求，可以再点“术语配置”维护 `glossary.json`
8. 选择 `.md` 或 `.dita` 文件和输出目录
9. 如有需要，再调整翻译方向
10. 点击“开始翻译”

大多数用户第一次使用，不需要改别的配置。

补充：

- 发布 zip 文件名会带版本号
- Windows 下 `DocTranslationTool.exe` 的文件属性里也会写入版本号

如果你在 macOS 本地打包运行：

1. 运行 `bash ./scripts/build_macos.sh`
2. 打开 `dist-macos/DocTranslationTool-macos-<arch>/`
3. 编辑和 `DocTranslationTool.app` 同目录下的 `.env`，或者启动后用“模型配置”按钮修改
4. 启动 `DocTranslationTool.app`

macOS 打包版会从 `.app` 所在目录读取 `.env`、`settings.json` 和 `glossary.json`。

## Anthropic 兼容接口怎么填

如果你的服务是 Anthropic 兼容接口，最简单的写法如下：

```env
DOC_TRANS_PROVIDER=openai_compatible
DOC_TRANS_API_FORMAT=anthropic
DOC_TRANS_ANTHROPIC_VERSION=2023-06-01
DOC_TRANS_BASE_URL=https://your-service.example
DOC_TRANS_API_KEY=your_api_key_here
DOC_TRANS_MODEL=your_model_name
```

最容易填错的地方：

- `DOC_TRANS_API_FORMAT` 要填 `anthropic`
- `DOC_TRANS_BASE_URL` 一般不要自己再手动加 `/messages`
- `DOC_TRANS_ANTHROPIC_VERSION` 没特殊要求时保持默认即可

## 你会在界面里看到什么

- `模型状态：配置不完整`
  关键配置还没填全
- `模型状态：配置已加载，待检查连通性`
  配置已经读到，但还没真正请求接口
- `模型状态：正在检查接口连通性`
  程序正在验证接口是否可用
- `模型配置`
  可以直接在 GUI 里修改 `.env`，也可以先测试连通性再保存
- `术语配置`
  可以直接维护 `glossary.json`，保存后后续翻译任务会自动加载
- `翻译中：正在处理第 x/N 批`
  当前有批次在执行
- `翻译中：已完成批次 x/N`
  已经有批次返回结果，进度会继续推进

## 配置说明

当前支持这些配置来源：

- `.env`
- `settings.json`
- 运行时环境变量

优先级如下：

1. 运行时环境变量
2. `.env`
3. `settings.json`
4. 代码默认值

大多数用户最常改的是这些字段：

- `DOC_TRANS_BASE_URL`
- `DOC_TRANS_API_KEY`
- `DOC_TRANS_MODEL`
- `DOC_TRANS_BATCH_SIZE`
- `DOC_TRANS_PARALLEL_BATCHES`
- `DOC_TRANS_MAX_RETRIES`
- `DOC_TRANS_TEMPERATURE`
- `DOC_TRANS_MAX_TOKENS`

如果你是第一次使用，先只改前 3 个就够了。

如果你不想手改文件，也可以直接用 GUI 里的“模型配置”按钮去改这些常用项。

本地 macOS 打包版同样遵循这个配置优先级，只是运行时根目录是 `DocTranslationTool.app` 所在目录，而不是 `.app` 包内部。

## DITA 支持范围

当前版本已支持 `.dita` 文件的基础翻译流程，适合常见 topic/task 类内容：

- 会抽取可翻译的 XML 文本节点进行翻译
- 会尽量保留代码类标签、路径、文件名和技术常量
- 输出文件会继续保持 `.dita` 后缀

目前 README 里说的复杂文档稳定性优化，主要还是围绕 Markdown 打磨得更充分；DITA 支持已经接入主流程，但后续还可以继续扩展更复杂的标签和内容类型覆盖。

## 相关文档

- [README.md](./README.md)：英文首页说明
- [使用指南.md](./使用指南.md)：更完整、更偏实操的中文指南
- [PACKAGING.md](./PACKAGING.md)：桌面打包说明
- [CHANGELOG.md](./CHANGELOG.md)：版本更新记录

## 版本说明

- 运行时版本来自 `doc_translation_tool.__version__`
- 打包元数据会动态读取版本号
- 每次正式发版都会记录到 `CHANGELOG.md`
- 仓库主分支里可能已经包含比最新 Release 更新的改动，这些内容会先记录在 `Unreleased`
