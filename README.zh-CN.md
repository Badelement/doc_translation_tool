# 文档翻译工具

用于翻译单个 Markdown 文档的桌面工具，重点是保留 Markdown 结构，并让中文和英文技术文档可以更稳地双向转换。

[English](./README.md) | [简体中文](./README.zh-CN.md)

当前发布版本：`0.4.1`

## 项目简介

这个项目主要解决的是实际工作里的文档翻译问题：

- 一次翻译一个 `.md` 文件
- 支持 `中译英` 和 `英译中`
- 尽量保留 Markdown 结构、占位符、表格和 front matter 规则
- 支持 OpenAI 兼容和 Anthropic 兼容接口
- 支持批次并行翻译，改善大文档处理速度
- 在 GUI 中提供更清晰的模型状态、连通性状态和批次进度反馈

## 当前已实现

- 单文件 Markdown 翻译
- 自动识别常见中英文文件并切换推荐翻译方向
- 可配置的批次并行翻译
- 启动后先检查模型配置是否完整
- 开始翻译后检查接口连通性
- 按批次显示翻译进度和完成情况
- 输出新文件，不覆盖源文件

## 快速开始

如果你使用的是 Windows 打包版：

1. 解压整个 `DocTranslationTool-win64.zip`
2. 打开 `dist\DocTranslationTool\`
3. 编辑 `DocTranslationTool.exe` 同目录下的 `.env`
4. 至少填好这 3 项：

```env
DOC_TRANS_BASE_URL=你的接口地址
DOC_TRANS_API_KEY=你的API Key
DOC_TRANS_MODEL=你要用的模型名
```

5. 启动 `DocTranslationTool.exe`
6. 先看左下角“模型状态”
7. 选择 `.md` 文件和输出目录
8. 如有需要，调整翻译方向
9. 点击“开始翻译”

## 你会在界面里看到什么

- `模型状态：配置不完整`
  说明关键配置还没填全
- `模型状态：配置已加载，待检查连通性`
  说明本地配置已经读到，但还没真正访问接口
- `模型状态：正在检查接口连通性`
  说明程序已经开始验证接口
- `翻译中：正在处理第 x/N 批`
  说明当前有批次正在跑
- `翻译中：已完成批次 x/N`
  说明已经有批次返回结果，进度条会继续推进

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

最常改的模型相关字段：

- `DOC_TRANS_BASE_URL`
- `DOC_TRANS_API_KEY`
- `DOC_TRANS_MODEL`
- `DOC_TRANS_BATCH_SIZE`
- `DOC_TRANS_PARALLEL_BATCHES`

## 相关文档

- [README.md](./README.md)：英文首页说明
- [使用指南.md](./使用指南.md)：面向使用者的详细中文指南
- [GitHub使用指南.md](./GitHub使用指南.md)：这个项目的 GitHub 使用和发版说明
- [PACKAGING.md](./PACKAGING.md)：Windows 打包说明
- [CHANGELOG.md](./CHANGELOG.md)：版本更新记录

## 版本说明

- 运行时版本来自 `doc_translation_tool.__version__`
- 打包元数据会动态读取版本号
- 每次正式发版都会记录到 `CHANGELOG.md`
