---
title: Sample Document
author: 张三
desc: |
  Startup Guide
  Used to verify regression samples.
---

# Flashing Guide `boot0`

Please see [User Guide](docs/guide.md) and ![Flowchart](figures/flow.png).

The value of ```CONFIG_SPINOR_LOGICAL_OFFSET``` must stay aligned with ```bootpackage```.

:::warning
Before using `boot0`, please confirm that U-Boot is configured correctly.
:::

| Name | Description |
| --- | --- |
| boot0 | Boot file |
| env | Environment variable |

```bash
make menuconfig
```
