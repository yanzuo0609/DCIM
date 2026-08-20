---
title: Model Design Redesign
project: RackDCIM Pro
version: 1.2.0
status: Active
date: 2026-08-17
---

# 模型设计（原设备定义）重设计

## 信息架构

```
网络设计
├── 模型设计
│     文件夹 / 项目（树）
│       └── 模型（分类 + 子类型 + 属性 + 面板 + 仿真映射）
├── 拓扑设计
│     拓扑项目 ──绑定──▶ 模型根目录
│       └── 拓扑图（画布实例 + 连线 + 实验室会话）
└── 接口设计
```

## 模板 → 拓扑 → 仿真

| 层级 | 含义 |
| --- | --- |
| 模型设计项目/文件夹 | 规格与面板模板库 |
| 拓扑项目 (`NetworkProject`) | 通过 `model_root_folder_id` 绑定模型根目录 |
| 设计模型 (`NetworkDesignModel`) | 可发布模板；含 `sim_image` 等仿真字段 |
| 拓扑节点 (`NetworkNode`) | 画布实例，带 `design_model_id` |
| 实验室会话 (`NetworkLabSession`) | 与 Eve-NG Lab 的同步/启停状态 |

流程：

1. 在「模型设计」定义并发布设备模型（可选填写 Eve-NG 镜像名）
2. 在「拓扑设计」选择拓扑项目，关联对应模型项目/文件夹
3. 新建拓扑，从模型库拖放/点击放置到画布，保存布局
4. 仿真引擎默认 `LAB_ENGINE=mock`（本地内存，无需 Eve-NG）。连接真实 Eve-NG 时设置：
   - `LAB_ENGINE=eve-ng`
   - `EVE_NG_BASE_URL=https://your-eve-host`
   - 可选：`EVE_NG_USER` / `EVE_NG_PASSWORD` / `EVE_NG_LAB_PATH`
   然后在拓扑页同步实验室并启动仿真。

## 分类与子类型

| 分类 category | 子类型 subtype |
| --- | --- |
| server | compute / storage / hpc |
| network | switch / router / load_balancer / optical_gate |
| security | firewall / vpn / ddos / ips / ids / optical_gate / host_audit / database_audit / net_audit / crypto |
| software | cloud / bigdata / mysql |

## 专业模型预设库

模型新建窗口内置 15 个可编辑预设，选择后自动生成硬件属性、面板与稳定接口编号：

- 服务器：1U 通用计算、2U 虚拟化、2U 存储、4U GPU/HPC。
- 交换机：48 口千兆接入、48 口万兆接入、模块化汇聚、100G 核心。
- 安全设备：防火墙、IPS、IDS、VPN、光闸、主机审计、数据库审计、网络审计。
- 预设只是起点，所有属性、板卡、接口编号和仿真图标仍可手动调整；发布后供批量拓扑复用。
## 属性（attributes JSON）摘要

- **server**：CPU 路数/颗数、内存、扩展 Slot、电源、BMC/USB、前后硬盘槽
- **network**：交换机角色、上下联口数/位置、风扇/电源
- **security**：业务口、Control/HA/MGMT、CPU/内存/磁盘
- **software**：版本、组件、兼容 OS、授权
- **仿真（各类共用）**：`sim_engine`、`sim_image`、`sim_icon`、`sim_ram`、`sim_cpu`

## 服务器与安全设备面板规范（1.3）

- 服务器 1U / 2U / 4U 使用接近实际 19 英寸机箱比例的前后面板；背板管理口、VGA、USB 与板载 LOM 固定在底部接口区。
- PCIe 插槽不再等同于“PCIe 光口”，每槽可选空挡板、RAID 卡、2/4 口电口网卡、2/4 口光口网卡；速率按卡独立选择，电口支持 1/10GE，光口支持 10/25/40/100GE。
- PCIe 端口 ID 使用 `pcie{slot}-p{index}`，卡类型、介质、速率、模块随拓扑节点同步。
- 防火墙、IPS、IDS、VPN、光闸、主机审计、数据库审计、网络审计等使用差异化仿真面板和硬件默认值，原 Slot 网格收进“接口参数/自定义面板”。
- 安全接口命名空间使用 `sec-s{slot}-{kind}-p{index}`，保证模型、面板和拓扑中的接口唯一且可定位。
## 应用与拓扑

- 模型可绑定合同设备名称并「应用面板/规格」到台账
- 拓扑仅展示已绑定目录下的模型（含设备简图）；节点继承模型网络角色（CORE/AGG/ACCESS…），可在详情中覆盖，并支持 `device_group`
- **布线规则**（`network_wiring_rule.config` 结构化参数）：
  - 01 设备：Source/Target Role、Group、显式设备、Connection Type、Required
  - 02/03 链路：Link Count / Min / Max、Speed、Speed Mode、配对模式
  - 04 端口：Port Purpose、**端口池**、范围、口类型；PEER 口不参与普通业务布线
  - 05 冗余：A/B、设备/路径/机柜/板卡/端口多样性
  - 06/08 Peer-Link / LAG / Keepalive
  - 09/10 介质与距离：AUTO（≤3m DAC / ≤10m AOC / 否则光纤）可覆盖
  - 执行后写回 `NetworkLink`（含 connection_type、speed、LAG、冗余路径、介质等），保存拓扑后在「接口设计」连线表与 Excel 可见
- Eve-NG：后端代理同步 Lab；浏览器不直连凭证

### 批量拓扑与智能编排

- 批量放置模型时可直接指定设备组和网络角色，并按角色分层、组内相邻的紧凑算法自动排版。
- 画布保留单设备拖放、手工移动、手工连线；工具栏可随时重新执行「智能布局」。
- 「一键自动布线」只执行启用且分配方式为 `AUTO` 的规则；`MANUAL` / `HYBRID` 保留人工确认流程。
- 自动规则可按设备组限定范围，也可在整个拓扑中按角色执行，执行后统一保存节点与连线。
### 端口池与模型板卡/上联

模型属性驱动面板端口，布线按池选取：

| 端口池 | 模型来源 | layout / group.role | 典型 Purpose |
| --- | --- | --- | --- |
| `OPTICAL`（板卡光口） | `optical_card_count × optical_ports_per_card`（或 `downlink_count`） | `main` / `card`，标签 `1…N`，类型多为 `1g`/`10g` | DOWNLINK / SERVER |
| `UPLINK`（40/100G 上联） | `uplink_count` | `uplink`，标签 `U1…Un`，类型多为 `40_100g`（千兆上联可为 `10g`） | UPLINK / PEER / DAD |

- `source_port_pool` / `target_port_pool`：`AUTO | OPTICAL | UPLINK`
- **AUTO**：按 Purpose 推导——UPLINK/PEER/DAD → 上联池；DOWNLINK/SERVER → 板卡光口池
- 连接类型 UPLINK 默认：源池=上联、目的池=板卡光口；Speed Mode 用 MIN（两端速率可不同）
- 画布节点加载时按 `group.role` 补全 Purpose，保证旧拓扑也能按池匹配

### 布线示例

| 规则 | Source → Target | Connection | Link Count | 源池 → 目的池 |
| --- | --- | --- | --- | --- |
| 核心上联 | CORE → AGG | UPLINK | 2 | UPLINK → OPTICAL |
| 接入服务器 | ACCESS → SERVER | SERVER | 2 + A/B + 设备多样性 | OPTICAL → OPTICAL(SERVER) |
| 堆叠互联 | ACCESS ↔ ACCESS | PEER | Peer-Link=2 | UPLINK → UPLINK |
