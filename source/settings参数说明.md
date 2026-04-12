# settings 参数说明

这份文档专门解释 `settings.json` 里的各个字段是什么意思、什么时候需要改、以及它和 `.env` 的对应关系。

先说结论：

- 大多数用户只需要修改 `.env`
- `settings.json` 更适合放“不常变的高级默认参数”
- 同一个参数如果同时写在 `.env` 和 `settings.json`，以 `.env` 为准

配置优先级从高到低是：

1. 运行时环境变量
2. `.env`
3. `settings.json`
4. 程序内置默认值

## 1. 一个完整示例

当前仓库中的 `settings.example.json` 内容如下：

```json
{
  "llm": {
    "provider": "openai_compatible",
    "api_format": "openai",
    "anthropic_version": "2023-06-01",
    "base_url": "https://example.internal/api/v1",
    "api_key": "your_api_key_here",
    "model": "internal-translate-model",
    "timeout": 60,
    "connect_timeout": 10,
    "read_timeout": 60,
    "max_retries": 2,
    "batch_size": 8,
    "parallel_batches": 2,
    "temperature": 0.2,
    "max_tokens": null
  },
  "markdown": {
    "front_matter_translatable_fields": ["title", "subtitle", "desc"]
  }
}
```

## 2. `llm` 字段说明

### `llm.timeout`

- 含义：整个 HTTP 请求的总超时时间，单位秒
- 默认值：`60`
- 对应 `.env`：`DOC_TRANS_TIMEOUT`
- 是否建议普通用户修改：按需

它控制的是一次请求从开始到结束的总等待时间。

建议：

- 接口响应稳定时，默认值通常够用
- 如果大批次翻译经常因为超时失败，可以适当调大到 `90` 或 `120`
- 不要盲目调得特别大，否则真正卡住时要等更久

### `llm.connect_timeout`

- 含义：建立连接时允许等待的时间，单位秒
- 默认值：`10`
- 对应 `.env`：`DOC_TRANS_CONNECT_TIMEOUT`

它主要管“能不能连上服务”，不管模型生成内容花多久。

建议：

- 网络环境差、代理链路长、跨区访问时，可以适当增大
- 大多数情况下保持默认即可

### `llm.read_timeout`

- 含义：连接建立后，等待服务端返回内容的时间，单位秒
- 默认值：`60`
- 对应 `.env`：`DOC_TRANS_READ_TIMEOUT`

它更接近“模型开始生成并返回内容要等多久”。

建议：

- 大文档、慢模型、服务高峰期，可以适当调大
- 如果接口经常慢，但不是连不上，优先考虑调这个，而不是 `connect_timeout`

### `llm.max_retries`

- 含义：单个批次失败后，最多再重试多少次
- 默认值：`2`
- 对应 `.env`：`DOC_TRANS_MAX_RETRIES`

实际效果：

- `2` 的意思不是“总共只请求 2 次”
- 而是“第一次失败后，额外再试 2 次”，也就是最多尝试 3 次

建议：

- 普通情况保持 `2`
- 如果你的接口偶发抖动较多，可以改成 `3`
- 如果你很在意速度，且接口本身比较稳定，可以降到 `1`
- 不建议设太高，否则失败批次会拖慢整篇文档

### `llm.batch_size`

- 含义：一次请求里打包多少个文本片段一起翻译
- 默认值：`8`
- 对应 `.env`：`DOC_TRANS_BATCH_SIZE`

这是影响成功率和速度最明显的参数之一。

怎么理解：

- 值越大：单次请求装的内容越多，理论吞吐更高
- 值越小：每次请求更轻，复杂文档更稳，但总请求数会更多

建议：

- 小文档、普通文档：`8` 通常可以
- 大型技术文档：优先试 `4`
- 特别复杂、占位符很多、表格很多的文档：可以试 `2` 到 `4`

### `llm.parallel_batches`

- 含义：允许同时并行跑多少个批次请求
- 默认值：`2`
- 对应 `.env`：`DOC_TRANS_PARALLEL_BATCHES`

怎么理解：

- 值越大：速度可能更快，但更容易触发限流、超时或服务端抖动
- 值越小：更稳，但整体耗时可能增加

建议：

- 首次跑复杂大文档：先用 `1`
- 接口比较稳时：可以用 `2`
- 如果你们服务经常报 `429`、限流、超时，不要继续加大，应该先降到 `1`

### `llm.temperature`

- 含义：模型生成时的随机性
- 默认值：`0.2`
- 对应 `.env`：`DOC_TRANS_TEMPERATURE`

对翻译任务来说，这个值通常越低越稳。

建议：

- 技术文档翻译建议保持低值，常见范围 `0.0` 到 `0.3`
- 不建议为了“文笔更活”把它调高
- 如果你很在意术语稳定、格式稳定，宁可更低一些

### `llm.max_tokens`

- 含义：限制单次请求返回内容的最大 token 数
- 默认值：不设置
- 对应 `.env`：`DOC_TRANS_MAX_TOKENS`
- 是否出现在示例文件中：当前没有

建议：

- 普通用户通常不需要配
- 如果你的服务端要求显式限制输出长度，或者某些模型对超长返回不稳定，可以考虑设置
- 设太小会导致输出被截断，不建议随便填写

### `llm.validation_mode`

- 含义：翻译结果验证模式，控制对残留语言和占位符顺序的检查严格程度
- 默认值：`balanced`
- 对应 `.env`：`DOC_TRANS_VALIDATION_MODE`
- 可选值：`strict`、`balanced`、`lenient`

三种模式的区别：

- `strict`：严格模式，适合普通文档。残留语言阈值 3 词，要求占位符严格顺序，批次拆分最小 1 段
- `balanced`：平衡模式（默认），适合大多数场景。残留语言阈值 5 词，允许占位符集合匹配，批次拆分最小 2 段
- `lenient`：宽松模式，适合技术文档。残留语言阈值 8 词，允许占位符重排序，批次拆分最小 3 段

建议：

- 普通文档保持默认 `balanced`
- 翻译技术文档（大量英文术语、代码、路径）时使用 `lenient`
- 对翻译质量要求极高时使用 `strict`

### `llm.residual_language_threshold`

- 含义：翻译结果中允许残留的源语言词数阈值
- 默认值：根据 `validation_mode` 自动设置（strict: 3, balanced: 5, lenient: 8）
- 对应 `.env`：`DOC_TRANS_RESIDUAL_LANGUAGE_THRESHOLD`

说明：

- 中译英时，检查翻译结果中占位符外是否残留过多中文
- 英译中时，检查翻译结果中占位符外是否残留过多英文
- 技术文档中常见的专业术语（如 API、SDK、Linux）不会被误判

建议：

- 通常不需要单独配置，由 `validation_mode` 自动控制
- 如果技术文档仍频繁重试，可以适当调大（如 10-15）

### `llm.allow_placeholder_reorder`

- 含义：是否允许翻译结果中占位符顺序与原文不同
- 默认值：根据 `validation_mode` 自动设置（strict: false, balanced: false, lenient: true）
- 对应 `.env`：`DOC_TRANS_ALLOW_PLACEHOLDER_REORDER`

说明：

- `false`：要求占位符顺序与原文完全一致（或使用集合比较）
- `true`：允许占位符重新排序，只要数量和内容匹配即可

建议：

- 通常不需要单独配置，由 `validation_mode` 自动控制
- 翻译包含方向性关键词（如"从 A 到 B"）的句子时，系统会自动使用严格顺序验证

### `llm.min_batch_split_size`

- 含义：批次拆分时的最小段落数，防止过度拆分
- 默认值：根据 `validation_mode` 自动设置（strict: 1, balanced: 2, lenient: 3）
- 对应 `.env`：`DOC_TRANS_MIN_BATCH_SPLIT_SIZE`

说明：

- 当批次翻译失败时，系统会尝试拆分成更小批次重试
- 此参数控制拆分的最小粒度，避免拆得过碎影响翻译质量

建议：

- 通常不需要单独配置，由 `validation_mode` 自动控制
- 如果大文档频繁失败，可以适当调小（但不建议小于 1）

## 3. `markdown` 字段说明

### `markdown.front_matter_translatable_fields`

- 含义：Markdown front matter 里哪些字段允许被翻译
- 默认值：`["title", "subtitle", "desc"]`
- 对应 `.env`：`DOC_TRANS_FRONT_MATTER_FIELDS`

什么是 front matter：

```yaml
---
title: 示例标题
subtitle: 示例副标题
desc: 这里是简介
author: 张三
---
```

这个配置的意思是：

- `title`、`subtitle`、`desc` 这些字段的值可以送去翻译
- 没在列表里的字段，默认更倾向于保持原样

当前默认值比较适合大多数文档，因为：

- 标题类字段通常需要翻译
- `author`、`date`、`version`、`id` 这类字段通常不应该随便翻

建议：

- 如果你的 front matter 里还有 `summary`、`abstract` 这类自然语言字段，也可以加进去
- 如果某些字段本质上是标识符、版本号、内部 key，不要加进去

`.env` 写法示例：

```env
DOC_TRANS_FRONT_MATTER_FIELDS=title,subtitle,desc,summary
```

## 4. `settings.json` 和 `.env` 的对应关系

常见字段对照如下：

| `settings.json` 路径                          | `.env` 变量                       | 默认值                   | 说明                  |
| ------------------------------------------- | ------------------------------- | --------------------- | ------------------- |
| `llm.provider`                              | `DOC_TRANS_PROVIDER`            | `openai_compatible`   | 客户端类型               |
| `llm.api_format`                            | `DOC_TRANS_API_FORMAT`          | `openai`              | 请求格式                |
| `llm.anthropic_version`                     | `DOC_TRANS_ANTHROPIC_VERSION`   | `2023-06-01`          | Anthropic 兼容版本头     |
| `llm.base_url`                              | `DOC_TRANS_BASE_URL`            | 空                     | 接口地址                |
| `llm.api_key`                               | `DOC_TRANS_API_KEY`             | 空                     | 接口密钥                |
| `llm.model`                                 | `DOC_TRANS_MODEL`               | 空                     | 模型名                 |
| `llm.timeout`                               | `DOC_TRANS_TIMEOUT`             | `60`                  | 总超时                 |
| `llm.connect_timeout`                       | `DOC_TRANS_CONNECT_TIMEOUT`     | `10`                  | 建连超时                |
| `llm.read_timeout`                          | `DOC_TRANS_READ_TIMEOUT`        | `60`                  | 读超时                 |
| `llm.max_retries`                           | `DOC_TRANS_MAX_RETRIES`         | `2`                   | 批次失败重试次数            |
| `llm.batch_size`                            | `DOC_TRANS_BATCH_SIZE`          | `8`                   | 每请求片段数              |
| `llm.parallel_batches`                      | `DOC_TRANS_PARALLEL_BATCHES`    | `2`                   | 并行批次数               |
| `llm.temperature`                           | `DOC_TRANS_TEMPERATURE`         | `0.2`                 | 随机性                 |
| `llm.max_tokens`                            | `DOC_TRANS_MAX_TOKENS`          | 不设置                   | 最大返回长度              |
| `llm.validation_mode`                       | `DOC_TRANS_VALIDATION_MODE`     | `balanced`            | 验证模式（strict/balanced/lenient） |
| `llm.residual_language_threshold`           | `DOC_TRANS_RESIDUAL_LANGUAGE_THRESHOLD`  | 5（根据模式自动设置）          | 残留语言词数阈值            |
| `llm.allow_placeholder_reorder`             | `DOC_TRANS_ALLOW_PLACEHOLDER_REORDER` | false（根据模式自动设置）   | 是否允许占位符重排序          |
| `llm.min_batch_split_size`                  | `DOC_TRANS_MIN_BATCH_SPLIT_SIZE`      | 2（根据模式自动设置）          | 批次拆分最小段落数           |
| `markdown.front_matter_translatable_fields` | `DOC_TRANS_FRONT_MATTER_FIELDS` | `title,subtitle,desc` | 可翻译 front matter 字段 |

## 5. 推荐配置

### 日常稳定配置

适合大多数普通文档：

```json
{
  "llm": {
    "batch_size": 8,
    "parallel_batches": 2,
    "max_retries": 2,
    "timeout": 60,
    "connect_timeout": 10,
    "read_timeout": 60,
    "temperature": 0.2
  },
  "markdown": {
    "front_matter_translatable_fields": ["title", "subtitle", "desc"]
  }
}
```

### 复杂技术文档优先稳

适合表格多、路径多、内联代码多、占位符多的大文档：

```json
{
  "llm": {
    "batch_size": 4,
    "parallel_batches": 1,
    "max_retries": 2,
    "timeout": 90,
    "connect_timeout": 10,
    "read_timeout": 90,
    "temperature": 0.1,
    "validation_mode": "lenient"
  }
}
```

说明：
- 使用 `lenient` 验证模式，放宽对技术术语和占位符顺序的检查
- 降低并发度和批次大小，提高稳定性

### 接口容易限流时

如果经常碰到 `429` 或高峰期不稳定：

```json
{
  "llm": {
    "batch_size": 4,
    "parallel_batches": 1,
    "max_retries": 3
  }
}
```

## 6. 最后的使用建议

- 想改接口地址、API Key、模型名，优先改 `.env`
- 想固定一套偏稳定或偏保守的高级参数，才去写 `settings.json`
- `settings.json` 不需要把所有字段都抄一遍，只写你真正要覆盖的字段
- 如果你发现复杂文档经常在后段重试很多次，优先先把 `batch_size` 和 `parallel_batches` 调小
- `temperature` 对翻译任务通常不是越高越好，技术文档更适合低值

如果你只是想先跑通工具，最小化做法仍然是：

1. 先只改 `.env`
2. 跑通一次
3. 只有在大文档稳定性或速度不合适时，再加 `settings.json`
