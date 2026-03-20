---
title: 示例文档
author: 张三
desc: |
  启动说明
  用于验证回归样例。
---

# 烧录说明 `boot0`

请查看 [用户手册](docs/guide.md) 和 ![流程图](figures/flow.png)。

参数```CONFIG_SPINOR_LOGICAL_OFFSET```需要和```bootpackage```保持一致。

:::warning
使用 `boot0` 前，请确认 U-Boot 配置正确。
:::

| 名称 | 说明 |
| --- | --- |
| boot0 | 启动文件 |
| env | 环境变量 |

```bash
make menuconfig
```
