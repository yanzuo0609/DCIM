---
title: Layout Engine Design Specification
project: RackDCIM Pro
version: 1.0.0
status: Draft
author: Enzo
date: 2026-07-16
category: Layout Engine
---

# Layout Engine Design Specification

> RackDCIM Pro
>
> Automatic Rack Layout Engine

---

# Revision History

| Version | Date       | Author | Description     |
| ------- | ---------- | ------ | --------------- |
| 1.0.0   | 2026-07-16 | Enzo   | Initial Version |
| 1.1.0   | 2026-07-17 | Enzo   | Clarify room slot numbering vs U-layout |

---

# Table of Contents

1. Engine Overview
2. Design Goals
3. Core Concepts
4. Data Model
5. Layout Rules
6. Placement Algorithm
7. Conflict Detection
8. Capacity Calculation
9. Numbering Strategy
10. Reservation Strategy
11. Batch Layout
12. Import Workflow
13. Output Model
14. Performance Design
15. Future AI Layout

---

# 1 Engine Overview

Layout Engine 是 RackDCIM 的核心计算模块。

负责：

- 机房机柜位布局与编号（Room 层）
- 自动设备上架
- U位计算
- 冲突检测
- 自动编号
- SVG坐标生成
- Excel绘图数据生成
- Dashboard容量统计

Engine 不负责：

- 数据库存储
- 页面展示
- SVG绘制

---

## Room 机柜位布局与编号（V1 已实现）

与「设备 U 位布局」分离：Room 决定机柜在机房中的网格位置与编号；Layout Engine 的 U 位算法再决定设备在机柜内的位置。

| 概念 | 说明 |
| ---- | ---- |
| row_layout | 每排机柜数量，如 `[6,6,8,4]` |
| layout_mode | auto：均匀 `rows×cols`；manual：自定义每排 |
| code_mode | auto / custom |
| code_prefix | 单字母 `A` 起按排递增，或范围 `A-D` / `A-BZ`（Excel 字母） |
| slot_codes | 二维编号矩阵，如 `[["A01","A02"],["B01","B02"]]` |

自动编号示例（3 列，前缀 `A`）：

```
A01 A02 A03
B01 B02 B03
C01 C02 C03
```

辅助函数（`schemas/infrastructure.py`）：`expand_row_prefixes`、`generate_slot_codes`、`normalize_row_layout`。

机柜创建时 `(row_no, column_no)` 必须落在 `row_layout` 内且空闲。

---

# 2 Design Goals

必须保证：

✓ 自动布局

✓ 零冲突

✓ 高性能

✓ 可回滚

✓ 可重算

✓ 可配置

✓ 可扩展

---

# 3 Core Concepts

## Rack

一个机柜：

```
42U

46U

48U

52U
```

每个Rack：

```
编号

名称

总U

位置

方向
```

---

## U Position

U位编号：

```
42

41

40

...

3

2

1
```

遵循：

Bottom → Top

编号：

1~42

显示：

42~1

---

## Device

设备属性：

```
Device Name

Height(U)

Depth

Weight

Power

Install Direction

Priority
```

---

## Occupancy

每一个U位：

```
FREE

USED

RESERVED

BLOCKED
```

---

# 4 Data Model

```text
Rack

↓

Slot

↓

Device
```

Slot：

```text
u_position

status

device_id
```

Device：

```text
height_u

install_type

weight

priority
```

---

# 5 Layout Rules

## Rule 1

设备必须连续占用U位。

例如：

```
4U

占：

10

11

12

13
```

禁止：

```
10

11

13

14
```

---

## Rule 2

禁止重叠。

任何两个设备：

```
U Position

不能重复
```

---

## Rule 3

禁止越界。

例如：

```
42U

设备：

4U

起始：

40

非法
```

---

## Rule 4

允许预留。

例如：

```
Storage

上方预留2U
```

配置：

```yaml
reserve_above:2
reserve_below:1
```

---

## Rule 5

支持安装方向。

```
Front

Rear
```

支持：

双面机柜。

---

# 6 Placement Algorithm

默认算法：

```
Bottom First
```

流程：

```
Device List

↓

Sort

↓

Find Available Slot

↓

Conflict Check

↓

Reserve Space

↓

Commit

↓

Generate Layout
```

排序：

```
Priority

↓

Height

↓

Weight

↓

Name
```

---

## Supported Algorithms

### Bottom First

默认。

### Top First

从42U开始。

### Center Balance

重量平衡。

### Power Balance

均衡功耗。

### Custom Rule

用户规则。

---

# 7 Conflict Detection

检查：

```
U冲突

设备重叠

越界

方向

预留冲突
```

输出：

```json
{
  "status":"conflict",
  "rack":"Rack-001",
  "device":"GPU-08",
  "u_position":17,
  "reason":"Occupied"
}
```

---

# 8 Capacity Calculation

计算：

```
Total U

Used U

Reserved U

Free U

Usage %

Remaining %
```

例如：

```
42U

Used

30

Reserved

2

Free

10

Usage

71.43%
```

---

# 9 Numbering Strategy

## 机房机柜位编号（V1）

Room 层：

- auto：`{排字母}{列序号}`，如 `A01`、`B02`；前缀可为单字母或范围 `A-D` / `A-BZ`
- custom：完整 `slot_codes` 矩阵，机房内唯一

机柜 `code`/`name` 创建时可默认取所选机柜位编号。

## 设备 / 资产编号（规划）

支持：

```
Rack001 / Server001
Prefix + Padding + Step
```

例如：`GPU001`、`GPU002`。

---

# 10 Reservation Strategy

支持：

设备上下预留。

例如：

```
Storage

Above

2U

Below

1U
```

GPU：

```
Above

1U
```

Network：

```
No Reserve
```

---

# 11 Batch Layout

支持：

Excel：

```
100

Rack

↓

5000

Device
```

流程：

```
Import

↓

Validate

↓

Layout

↓

Generate

↓

Save

↓

SVG

↓

Dashboard
```

支持：

事务。

失败：

全部回滚。

---

# 12 Import Workflow

支持：

Excel

CSV

JSON

导入：

```
Read

↓

Validate

↓

Normalize

↓

Layout

↓

Conflict

↓

Commit

↓

Export Result
```

---

# 13 Output Model

Engine 输出：

```json
{
  "rack":"Rack001",
  "device":"GPU001",
  "u_start":5,
  "u_end":8,
  "height":4,
  "x":10,
  "y":650,
  "width":220,
  "height_px":80
}
```

SVG：

直接消费。

Excel：

直接消费。

Dashboard：

直接消费。

---

# 14 Performance Design

目标：

```
500 Rack

10000 Device

Layout

<5s
```

SVG：

```
500 Rack

<2s
```

支持：

```
Parallel Layout
```

支持：

```
Incremental Layout
```

---

# 15 Future AI Layout

未来增加：

AI：

根据：

```
重量

功耗

散热

风道

维护频率

网络位置
```

自动推荐：

```
最佳机柜

最佳U位

最佳安装方向
```

支持：

LLM：

```
OpenAI

DeepSeek

Qwen

Claude
```

Agent：

```
AI Capacity Planner

AI Rack Planner

AI Data Center Optimizer
```

---

# Appendix A

## Engine Interface

```python
layout()

validate()

rollback()

reserve()

preview()

generate_svg()

export_excel()
```

---

# Appendix B

## Layout Status

| Status   | Description |
| -------- | ----------- |
| FREE     | 空闲        |
| USED     | 已占用      |
| RESERVED | 预留        |
| BLOCKED  | 禁用        |
| ERROR    | 异常        |

---

# References

- docs/03-Domain-Model.md
- docs/04-Database-Design.md
- docs/05-API-Design.md
- docs/09-SVG-Engine.md

---