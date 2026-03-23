# 文档翻译工具

用于翻译单个 Markdown 文档的桌面工具。重点是尽量保留 Markdown 结构，并让中英文技术文档的双向翻译更稳一些。

[English](./README.md) | [简体中文](./README.zh-CN.md)

当前发布版本：[v0.4.3](https://github.com/Badelement/doc_translation_tool/releases/tag/v0.4.3)

## 项目简介

这个工具主要解决的是“把一个 Markdown 技术文档稳一点地翻译出来”。

它适合这些场景：

- 一次翻译一个 `.md` 文件
- 支持 `中译英` 和 `英译中`
- 尽量保留 Markdown 结构、表格、占位符和 front matter
- 支持 OpenAI 兼容接口和 Anthropic 兼容接口
- 处理大文档时，可以按批次并行翻译
- GUI 会显示配置状态、接口检查状态和批次进度

## 当前已实现

- 单文件 Markdown 翻译
- 自动识别常见中英文内容并推荐翻译方向
- 可配置的批次大小和并发批次数
- 启动时先检查关键配置是否齐全
- 开始翻译时再检查接口连通性
- 按批次显示进度和完成情况
- 输出新文件，不覆盖原文件

## 快速开始

如果你使用的是 Windows 打包版，最快这样开始：

1. 解压整个 `DocTranslationTool-win64.zip`
2. 打开 `dist\DocTranslationTool\`
3. 编辑 `DocTranslationTool.exe` 同目录下的 `.env`
4. 先只填这 3 项：

```env
DOC_TRANS_BASE_URL=你的接口地址
DOC_TRANS_API_KEY=你的API Key
DOC_TRANS_MODEL=你要用的模型名
```

5. 启动 `DocTranslationTool.exe`
6. 先看左下角“模型状态”
7. 选择 `.md` 文件和输出目录
8. 如有需要，再调整翻译方向
9. 点击“开始翻译”

大多数用户第一次使用，不需要改别的配置。

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

如果你是第一次使用，先只改前 3 个就够了。

## 相关文档

- [README.md](./README.md)：英文首页说明
- [使用指南.md](./使用指南.md)：更完整、更偏实操的中文指南
- [PACKAGING.md](./PACKAGING.md)：Windows 打包说明
- [CHANGELOG.md](./CHANGELOG.md)：版本更新记录

## 版本说明

- 运行时版本来自 `doc_translation_tool.__version__`
- 打包元数据会动态读取版本号
- 每次正式发版都会记录到 `CHANGELOG.md`
