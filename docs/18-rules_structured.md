# 综合布线连线逻辑规则书（AI结构化版）

> 本文档为数据中心综合布线系统的连线逻辑规则，采用结构化格式编写，供AI引擎解析执行。
> 格式约定：YAML语义块 + 决策树 + 规则表，每条规则均有唯一ID便于引用。

---

## 0. 数据模型定义（Data Models）

### 0.1 设备模型 Device

```yaml
Device:
  id: string              # 设备唯一标识
  type: enum              # 设备类型
    - CORE_SWITCH         # 核心交换机
    - AGG_SWITCH          # 汇聚交换机
    - ACCESS_SWITCH_10G   # 万兆接入交换机
    - ACCESS_SWITCH_1G    # 千兆接入交换机
    - SERVER              # 服务器
    - SECURITY_DEVICE     # 安全设备（防火墙/WAF/IDS等）
    - BMC_SWITCH          # BMC管理交换机
  group_id: string|null   # 所属设备组ID，独立设备为null
  group_size: int         # 组内设备数量（独立设备=1）
  slots:                  # 板卡/插槽列表
    - slot_id: int        # slot编号
      interface_type: enum  # 接口类型
        - 10G_FIBER       # 万兆光口
        - 10G_COPPER      # 万兆电口
        - 25G_FIBER       # 25G光口
        - 40G_FIBER       # 40G光口
        - 100G_FIBER      # 100G光口
        - 1G_COPPER       # 千兆电口
        - GE_RJ45         # 千兆RJ45（含BMC/IPMI口）
      port_count: int     # 该slot上端口总数
      ports:              # 端口列表
        - port_id: int            # 端口编号（从0开始）
          status: enum            # OCCUPIED | FREE | RESERVED
          role: enum|null         # UPLINK | DOWNLINK | PEER_LINK | DAD | BMC | null
          media: enum             # FIBER | COPPER
          speed: enum             # 1G | 10G | 25G | 40G | 100G
          connected_to: string|null  # 已连接的对端端口标识
```

### 0.2 端口角色定义 PortRole

```yaml
PortRole:
  UPLINK:   "上联口 — 用于接入交换机连接核心/汇聚交换机"
  DOWNLINK: "下联口 — 用于核心/汇聚/接入交换机连接下级设备"
  PEER_LINK: "组内互联口 — 用于堆叠/M-LAG peer-link"
  DAD:      "双主检测口 — 用于堆叠DAD检测"
  BMC:      "带外管理口 — 连接服务器IPMI/BMC接口"
  SERVER_NIC: "服务器业务网卡口"
```

### 0.3 连线请求模型 LinkRequest

```yaml
LinkRequest:
  source:
    device_or_group: string      # 源设备/设备组ID
    port_role: enum              # 源端口角色（DOWNLINK等）
  target:
    device_or_group: string      # 目标设备/设备组ID
    port_role: enum              # 目标端口角色（UPLINK等）
  mode: enum                     # AUTO | MANUAL
  manual_selections: list|null   # 手动模式下用户指定的端口对列表
  constraint:
    media_match: bool            # 是否要求介质匹配（光纤↔光纤）
    speed_match: bool            # 是否要求速率匹配
    redundancy: bool             # 是否要求冗余（每台设备至少2条链路）
```

### 0.4 连线结果模型 LinkResult

```yaml
LinkResult:
  success: bool
  links:                         # 成功建立的连线列表
    - source_port: string        # "device_id/slot_id/port_id"
      target_port: string
      media: enum
      speed: enum
  errors:                        # 失败信息列表
    - code: string               # 错误码（见§6）
      device_id: string
      message: string
  warnings: list                 # 警告信息（如速率降级、介质不匹配等）
```

---

## 1. 场景分类决策树（Scenario Router）

```
输入: LinkRequest
│
├─ 源设备类型是 BMC_SWITCH？
│   └─ YES → 场景B1: BMC管理布线（§3）
│
├─ 源设备类型是 CORE_SWITCH / AGG_SWITCH？
│   │
│   ├─ 目标设备类型是 ACCESS_SWITCH？
│   │   │
│   │   ├─ 源为单台 且 目标为单台 → 场景C1（§4.1）
│   │   ├─ 源为组   且 目标为单台 → 场景C2（§4.2）
│   │   ├─ 源为组   且 目标为组   → 场景C3（§4.3）
│   │   └─ 源为组   且 目标为千兆接入 → 场景C4（§4.4）
│   │
│   └─ 目标设备类型是 CORE_SWITCH（另一组核心）？
│       └─ YES → 场景D2: 核心组间互联（§5.2）
│
├─ 源设备类型是 ACCESS_SWITCH？
│   │
│   ├─ 目标设备类型是 SERVER / SECURITY_DEVICE？
│   │   │
│   │   ├─ 源为单台 且 目标为单台 → 场景A1（§2.1）
│   │   ├─ 源为组   且 目标为单台 → 场景A2（§2.2）
│   │   └─ 源为组   且 目标为组   → 场景A3（§2.3）
│   │
│   └─ 目标设备类型是 ACCESS_SWITCH（同类型组内/组间）？
│       ├─ 同组 → 场景D1: 组内互联（§5.1）
│       └─ 不同组 → 场景D2: 组间互联（§5.2）
│
└─ 以上都不匹配 → 错误 ERR_UNSUPPORTED_TOPOLOGY
```

---

## 2. 场景A：接入交换机 → 服务器/安全设备

### 2.1 场景A1：单台交换机 → 单台服务器/安全设备

```yaml
scenario: A1
name: "单台接入交换机连接单台服务器/安全设备"
source:
  type: ACCESS_SWITCH (10G/1G)
  count: 1
  port_role: DOWNLINK  # 自动设定
target:
  type: SERVER | SECURITY_DEVICE
  count: 1

rules:
  # ===== 源端（交换机）端口选择 =====
  source_port_selection:
    auto:
      algorithm: SEQUENTIAL_SCAN
      start_port: 0
      direction: ASCENDING
      logic: |
        从交换机端口0开始顺序扫描：
        1. 检查端口状态是否为FREE
        2. 检查端口速率是否与目标设备匹配
        3. 检查端口介质是否与目标设备匹配
        4. 若以上均满足 → 选中该端口
        5. 若不满足 → 检查下一个端口
        6. 全部端口扫描完毕仍无可用 → 返回 ERR_NO_FREE_PORT

    manual:
      logic: |
        1. 展示交换机上所有状态为FREE的端口列表
        2. 用户手动选择一个端口号
        3. 校验所选端口与目标设备接口类型/速率/介质是否匹配
        4. 不匹配 → 返回 ERR_PORT_TYPE_MISMATCH

  # ===== 目标端（服务器）端口选择 =====
  target_port_selection:
    # 前置规则：端口池自动匹配
    pre_rule: |
      若目标为SERVER，端口以slot为单位组织：
      - 自动匹配slot上的端口数量形成"端口池"
      - 万兆交换机只能对接服务器的10G接口slot
      - 千兆交换机只能对接服务器的1G接口slot或BMC口

    auto:
      # 万兆交换机 → 服务器
      - condition: "source.type == ACCESS_SWITCH_10G"
        default_action: "使用服务器10G slot的第1个端口（slot1-port1）"
        fallback: "若slot1-port1被占用，按slot1-port2, slot2-port1...顺序查找"

      # 千兆交换机 → 服务器（BMC场景见§3）
      - condition: "source.type == ACCESS_SWITCH_1G"
        default_action: "使用服务器1G slot的第1个端口"

    manual:
      logic: |
        1. 用户选择目标设备的slot编号
        2. 系统展示该slot上FREE状态的端口
        3. 用户选择具体端口号
        4. 校验与源端口类型/速率/介质匹配

  # ===== 类型匹配约束 =====
  constraints:
    - rule: "10G交换机 ↔ 服务器10G接口（不可降级对接1G接口）"
    - rule: "1G交换机 ↔ 服务器1G接口"
    - rule: "介质必须匹配：光纤↔光纤，铜缆↔铜缆（除非使用光电转换模块）"
    - rule: "安全设备端口类型需与交换机端口速率一致"
```

### 2.2 场景A2：交换机组 → 单台服务器/安全设备

```yaml
scenario: A2
name: "交换机组（默认2台）连接单台服务器/安全设备"
source:
  type: ACCESS_SWITCH (10G/1G)
  count: N (默认2，可扩展)
  port_role: DOWNLINK
target:
  type: SERVER | SECURITY_DEVICE
  count: 1

rules:
  source_port_selection:
    auto:
      algorithm: PER_DEVICE_SEQUENTIAL
      logic: |
        对交换机组中的每台交换机独立执行：
        1. 该交换机从端口0开始顺序扫描
        2. 选中第一个FREE且类型/速率/介质匹配的端口
        3. 若该交换机无可用端口 → 返回 ERR_NO_FREE_PORT
           并在错误信息中指明是哪台交换机
      constraint: "每台交换机出1条线，共N条线连接到同一台服务器"

    manual:
      logic: "每台交换机手动选择1个FREE端口，共选N个"

  target_port_selection:
    # 核心逻辑：根据服务器slot数量与交换机数量的关系分流
    auto:
      # 获取服务器上与源交换机接口类型相同的slot列表
      step_1_identify: |
        扫描服务器所有slot，筛选出interface_type与源交换机匹配的slot：
        - 源为10G交换机 → 筛选所有10G接口的slot
        - 源为1G交换机 → 筛选所有1G接口的slot
        记匹配slot数量为 M，源交换机数量为 N

      # ── 情况2a：M >= N（slot数量充足）──
      step_2a_sufficient_slots:
        condition: "M >= N"
        algorithm: ONE_PORT_PER_SLOT
        logic: |
          每台交换机分别接入不同slot的空闲端口：
          1. 交换机1 → slot1的第1个FREE端口
          2. 交换机2 → slot2的第1个FREE端口
          3. 交换机k → slot_k的第1个FREE端口
          4. 若某slot的第1个端口被占用 → 使用该slot的下一个FREE端口
          5. 若整个slot端口全部被占用 → 切换到下一个可用slot
          6. 若所有slot都没有足够空闲端口 → ERR_INSUFFICIENT_PORTS

      # ── 情况2b：M < N 且 M > 0（slot不足，需复用）──
      step_2b_reuse_slots:
        condition: "0 < M < N"
        algorithm: ROUND_ROBIN_ACROSS_SLOTS
        logic: |
          slot数量不足以一一对应，按轮询方式复用slot：
          分配顺序示例（N=3台万兆交换机，M=2个万兆slot）：
            交换机1 → slot1-port1
            交换机2 → slot2-port1
            交换机3 → slot1-port2  ← 回到slot1使用第2个端口
          分配顺序示例（N=2台万兆交换机，M=1个万兆slot）：
            交换机1 → slot1-port1
            交换机2 → slot1-port2
          规则：
            1. 按slot顺序轮流分配，每个slot先占用低编号端口
            2. 若某slot所有端口用完 → 跳过该slot
            3. 若所有slot端口全部用完仍不够 → ERR_INSUFFICIENT_PORTS

      # ── 情况2c：M == 0（无匹配slot）──
      step_2c_no_match:
        condition: "M == 0"
        action: "弹出提示 ERR_NO_MATCHING_INTERFACE"

    manual:
      logic: |
        1. 源设备组有N台交换机 → 需要在服务器上选N个端口
        2. 用户可选择不同slot上的端口，也可选择同一slot上的不同端口
        3. 校验每个所选端口与对应交换机端口的类型/速率/介质匹配
        4. 若可用端口总数 < N → ERR_INSUFFICIENT_PORTS

  constraints:
    - rule: "每台交换机出且仅出1条线到目标服务器"
    - rule: "端口类型/速率/介质必须匹配"
    - rule: "同一slot可被多台交换机复用，但端口不可重复"
```

### 2.3 场景A3：交换机组 → 服务器/安全设备组

```yaml
scenario: A3
name: "交换机组连接服务器/安全设备组（数量任意）"
source:
  type: ACCESS_SWITCH (10G/1G)
  count: N
  port_role: DOWNLINK
target:
  type: SERVER | SECURITY_DEVICE
  count: M (任意数量)

rules:
  source_port_selection:
    auto:
      algorithm: PER_DEVICE_SEQUENTIAL
      logic: |
        对交换机组中的每台交换机独立执行：
        1. 从端口0开始顺序扫描，选中第一个FREE且匹配的端口
        2. 若某台交换机无可用端口 → ERR_NO_FREE_PORT（指明设备）

    manual:
      logic: |
        1. 用户可在源设备组中任意一台交换机上选择任意FREE接口
        2. 源设备组有N台设备 → 必须选择N条线路（每台至少1条）
        3. 每台交换机选择的端口数量可以不同，但每台至少1条

  target_port_selection:
    auto:
      algorithm: CROSS_CONNECT_MINIMAL
      logic: |
        服务器组中每台服务器分别从不同slot上最小号FREE端口连接
        到源设备组中每台交换机的最小号FREE端口：
        1. 对服务器组中的每台服务器_i (i=1..M)：
           a. 找到该服务器上类型匹配的slot
           b. 从最小slot编号的最小FREE端口开始选择
           c. 对应连接到交换机组中交换机_j的最小FREE端口
        2. 连线分配策略（以N台交换机、M台服务器为例）：
           - 若 N == M：一一对应，交换机_j ↔ 服务器_j
           - 若 N > M：每台服务器连接到多台交换机（保证每台交换机至少连1台服务器）
           - 若 N < M：每台交换机连接到多台服务器（保证每台服务器至少连1台交换机）
        3. 若任何一端无可用端口 → ERR_NO_FREE_PORT

    manual:
      logic: |
        1. 用户可选择服务器组中每台服务器的不同slot上的不同类型接口
        2. 若某台服务器slot不足 → 可选择相同slot上的不同端口
        3. 若所有服务器可用端口总数 < N（交换机数量）→ ERR_INSUFFICIENT_PORTS
        4. 每台服务器至少需要1条连线

  constraints:
    - rule: "源组每台交换机至少连接1条线到目标组"
    - rule: "目标组每台服务器至少连接1条线到源组"
    - rule: "端口类型/速率/介质必须匹配"
    - rule: "同一物理端口不可被重复使用"
```

---

## 3. 场景B：BMC管理布线

```yaml
scenario: B1
name: "BMC管理交换机 → 服务器IPMI/BMC接口"
source:
  type: ACCESS_SWITCH_1G (千兆交换机，用于BMC管理)
  count: 1或组
  port_role: BMC
target:
  type: SERVER
  count: 1或多台
  target_port: "服务器IPMI/BMC专用接口"

rules:
  port_selection:
    auto:
      algorithm: SEQUENTIAL_SCAN
      logic: |
        1. BMC交换机从端口0开始顺序连接
        2. 每个端口连接一台服务器的IPMI/BMC接口
        3. 端口编号严格递增：port0→server1_bmc, port1→server2_bmc, ...
        4. 若交换机端口用完 → ERR_NO_FREE_PORT
        5. 若服务器无BMC接口 → ERR_NO_BMC_INTERFACE

    manual:
      logic: "手动指定交换机端口到服务器BMC接口的对应关系"

  constraints:
    - rule: "BMC交换机必须为千兆（1G）"
    - rule: "目标端口为服务器专用IPMI/BMC接口，非业务网口"
    - rule: "BMC链路与业务链路物理隔离"
    - rule: "BMC网络建议独立VLAN/独立子网"
```

---

## 4. 场景C：核心/汇聚交换机 → 接入交换机

### 4.1 场景C1：单台核心/汇聚 → 单台接入交换机

```yaml
scenario: C1
name: "单台核心/汇聚交换机 → 单台万兆接入交换机"
source:
  type: CORE_SWITCH | AGG_SWITCH
  count: 1
  port_role: DOWNLINK  # 自动设定
target:
  type: ACCESS_SWITCH_10G
  count: 1
  port_role: UPLINK  # 自动设定

rules:
  source_port_selection:
    auto:
      algorithm: MIN_SLOT_MIN_PORT
      logic: |
        1. 在源交换机上找到类型匹配（与目标uplink接口类型一致）的最小slot编号
        2. 在该slot上从最小端口号开始扫描
        3. 选中第一个FREE端口
        4. 若该slot无空闲 → 切换到下一个同类型slot继续扫描
        5. 若所有slot都无空闲 → ERR_NO_FREE_PORT

    manual:
      logic: "用户手动选择源交换机上指定板卡（slot）的指定端口"

  target_port_selection:
    auto:
      algorithm: MIN_PORT_MATCH_TYPE
      logic: |
        1. 在目标交换机的UPLINK接口中，找到与源端口类型相同的接口
        2. 从最小端口号开始选择第一个FREE端口
        3. 若无空闲 → ERR_NO_FREE_PORT

    manual:
      logic: "用户手动选择目标交换机的UPLINK接口"

  constraints:
    - rule: "源端口类型（DOWNLINK）与目标端口类型（UPLINK）自动设定"
    - rule: "接口速率/介质必须匹配"
```

### 4.2 场景C2：核心/汇聚交换机组 → 单台接入交换机

```yaml
scenario: C2
name: "核心/汇聚交换机组 → 单台万兆接入交换机"
source:
  type: CORE_SWITCH | AGG_SWITCH
  count: N (组)
  port_role: DOWNLINK
target:
  type: ACCESS_SWITCH_10G
  count: 1
  port_role: UPLINK

rules:
  source_port_selection:
    auto:
      algorithm: PER_DEVICE_MIN_SLOT_MIN_PORT
      logic: |
        对源交换机组中每台交换机独立执行：
        1. 找到类型匹配的最小slot编号
        2. 在该slot上从最小端口号选择第一个FREE端口
        3. 每台交换机出1条线，共N条线

    manual:
      logic: |
        1. 用户可选择源交换机组中任意一台交换机的任意板卡的任意接口
        2. 源设备组有N台设备 → 必须选择N条线路（每台至少1条）

  target_port_selection:
    auto:
      algorithm: SEQUENTIAL_UPLINK_ASSIGN
      logic: |
        1. 目标交换机的UPLINK接口从最小编号开始自动分配
        2. 源交换机组中交换机1 → 目标UPLINK port_0
        3. 源交换机组中交换机2 → 目标UPLINK port_1
        4. 依此类推
        5. 若UPLINK接口不足 → ERR_INSUFFICIENT_PORTS

    manual:
      logic: "用户手动指定目标交换机的UPLINK接口，每条线对应一个UPLINK端口"

  constraints:
    - rule: "源组每台交换机出1条线到目标交换机的不同UPLINK端口"
    - rule: "UPLINK端口不可重复使用"
```

### 4.3 场景C3：核心/汇聚交换机组 → 接入交换机组

```yaml
scenario: C3
name: "核心/汇聚交换机组 → 万兆接入交换机组"
source:
  type: CORE_SWITCH | AGG_SWITCH
  count: N (组)
  port_role: DOWNLINK
target:
  type: ACCESS_SWITCH_10G
  count: M (组)
  port_role: UPLINK

rules:
  source_port_selection:
    auto:
      algorithm: PER_DEVICE_MIN_SLOT_MIN_PORT
      logic: |
        源交换机组中每台交换机：
        1. 找到最小slot编号的最小FREE端口
        2. 若该端口被占用 → 切换到下一个端口
        3. 依次连接到目标组中对应的交换机

    manual:
      logic: |
        1. 用户手动指定源组中哪台交换机的哪个接口
           连接到目标组中哪台交换机的哪个UPLINK接口
        2. 约束：所有源交换机都必须和目标交换机有连线
        3. 约束：所有目标交换机都必须和源交换机有连线

  target_port_selection:
    auto:
      algorithm: CROSS_GROUP_CONNECT
      logic: |
        目标组中每台交换机上联，分别连接到源设备组中的交换机：
        1. 目标交换机_j的UPLINK最小端口 → 源交换机_i的最小slot最小端口
        2. 分配策略：
           - 若 N >= M：每台目标交换机连接到至少1台源交换机
             额外的源交换机可连接到目标交换机的其他UPLINK端口（冗余）
           - 若 N < M：每台源交换机连接到多台目标交换机
        3. 若端口不足 → ERR_NO_FREE_PORT

  constraints:
    - rule: "确保源组每台交换机至少连接1台目标交换机"
    - rule: "确保目标组每台交换机至少连接1台源交换机"
    - rule: "除组内互联外，组间每台设备都应有连线"
```

### 4.4 场景C4：核心/汇聚交换机组 → 千兆接入交换机

```yaml
scenario: C4
name: "核心/汇聚交换机组（万兆）→ 千兆接入交换机（汇聚下联）"
source:
  type: CORE_SWITCH | AGG_SWITCH (万兆)
  count: 1或组
  port_role: DOWNLINK
target:
  type: ACCESS_SWITCH_1G (千兆)
  count: 1或组
  port_role: UPLINK

rules:
  # 遵循场景C1-C3相同原则
  base_rules: "继承§4.1-§4.3的端口选择逻辑"
  source_port_selection:
    auto_or_manual: "源交换机/组自动连接千兆交换机的UPLINK接口，或手动指定接口"
  target_port_selection:
    auto_or_manual: "千兆交换机UPLINK接口自动匹配或手动指定"

  special_constraint:
    - rule: "万兆核心交换机下联千兆接入交换机时，核心侧端口速率需支持降速至1G"
    - rule: "或核心侧使用千兆板卡端口进行连接"
    - rule: "当源或目标为设备组时，确保除组内设备间互联外，每台设备都有到对端的连线"

  constraints:
    - rule: "确保组间连通性：每台源设备至少连接1台目标设备，反之亦然"
    - rule: "速率匹配：若核心侧仅万兆端口，需确认对端千兆交换机支持万兆UPLINK或使用降速模块"
```

---

## 5. 场景D：交换机间互联

### 5.1 场景D1：组内交换机互联（堆叠/M-LAG）

```yaml
scenario: D1
name: "组内交换机互联（同型号交换机，做peer-link和DAD）"
source:
  type: ACCESS_SWITCH (同型号)
  count: 2（默认双机）
target:
  type: ACCESS_SWITCH (同型号)
  count: 2
  note: "源和目标为同一组内的两台交换机"

rules:
  auto:
    algorithm: RESERVED_PORT_INTERCONNECT
    logic: |
      1. UPLINK接口的最后2个端口自动互联：
         - UPLINK_port[-2] ↔ 对端 UPLINK_port[-2]  → PEER_LINK
         - UPLINK_port[-1] ↔ 对端 UPLINK_port[-1]  → DAD
      2. DOWNLINK接口的最后2个端口自动互联：
         - DOWNLINK_port[-2] ↔ 对端 DOWNLINK_port[-2]  → PEER_LINK（备用）
         - DOWNLINK_port[-1] ↔ 对端 DOWNLINK_port[-1]  → DAD（备用）
      3. 互联端口角色自动标记为 PEER_LINK 和 DAD
      4. 互联端口状态标记为 RESERVED（不再参与其他连线）

    port_mapping_example: |
      交换机A                          交换机B
      ┌──────────────┐                ┌──────────────┐
      │ UPLINK       │                │ UPLINK       │
      │  port 0      │                │  port 0      │
      │  port 1      │                │  port 1      │
      │  ...         │                │  ...         │
      │  port[-2] ───┼────────────────┼── port[-2]   │  ← PEER_LINK
      │  port[-1] ───┼────────────────┼── port[-1]   │  ← DAD
      └──────────────┘                └──────────────┘
      ┌──────────────┐                ┌──────────────┐
      │ DOWNLINK     │                │ DOWNLINK     │
      │  port 0      │                │  port 0      │
      │  ...         │                │  ...         │
      │  port[-2] ───┼────────────────┼── port[-2]   │  ← PEER_LINK(备)
      │  port[-1] ───┼────────────────┼── port[-1]   │  ← DAD(备)
      └──────────────┘                └──────────────┘

  constraints:
    - rule: "仅同型号、同组内的交换机执行组内互联"
    - rule: "互联端口固定为UPLINK和DOWNLINK的最后2个端口"
    - rule: "互联端口标记为RESERVED，不参与业务连线"
    - rule: "至少建立PEER_LINK和DAD各1条（推荐2条，分别在UPLINK和DOWNLINK上）"
```

### 5.2 场景D2：组间交换机互联（核心组之间/跨组互联）

```yaml
scenario: D2
name: "组间交换机互联（一组核心与另一组核心之间的连线）"
source:
  type: CORE_SWITCH | AGG_SWITCH (组A)
  count: N
target:
  type: CORE_SWITCH | AGG_SWITCH (组B)
  count: M

rules:
  auto:
    algorithm: CROSS_INTERCONNECT_LAST_PORTS
    logic: |
      1. 源组和目标组的每个板卡的最后2个接口分别交叉互联
      2. 交叉规则：
         源组设备A_slot_k_port[-2] ↔ 目标组设备B_slot_k_port[-2]
         源组设备A_slot_k_port[-1] ↔ 目标组设备B_slot_k_port[-1]
      3. 若源组和目标组设备数量不同：
         - N == M：一一对应交叉互联
         - N != M：确保每台设备至少有1条跨组连线

  manual:
    logic: |
      1. 用户手动选择源组和目标组的接口进行连线
      2. 约束：确保源组和目标组之间有足够的连通性
      3. 建议：每台设备至少1条跨组链路

  constraints:
    - rule: "跨组互联端口不使用RESERVED标记（非堆叠链路）"
    - rule: "推荐使用板卡尾部端口，避免与业务端口冲突"
    - rule: "跨组链路建议配置为Trunk模式，允许多VLAN通过"
```

---

## 6. 统一错误处理（Error Codes）

```yaml
error_codes:
  ERR_NO_FREE_PORT:
    code: "E001"
    message: "无可用端口"
    detail: "设备 {device_id} 上没有空闲且类型匹配的端口"
    action: "提示用户检查端口占用情况或增加设备"

  ERR_PORT_TYPE_MISMATCH:
    code: "E002"
    message: "端口类型不匹配"
    detail: "源端口类型({src_type})与目标端口类型({dst_type})不兼容"
    action: "提示用户选择匹配类型的端口"

  ERR_NO_MATCHING_INTERFACE:
    code: "E003"
    message: "缺少匹配的接口"
    detail: "目标设备上没有与源设备接口类型匹配的slot/端口"
    action: "提示用户检查设备配置或添加对应接口卡"

  ERR_INSUFFICIENT_PORTS:
    code: "E004"
    message: "端口数量不足"
    detail: "需要 {required} 个端口，但仅有 {available} 个可用"
    action: "提示用户增加设备或释放已占用端口"

  ERR_NO_BMC_INTERFACE:
    code: "E005"
    message: "服务器无BMC/IPMI接口"
    detail: "服务器 {server_id} 没有可用的IPMI/BMC管理接口"
    action: "提示用户检查服务器配置"

  ERR_UNSUPPORTED_TOPOLOGY:
    code: "E006"
    message: "不支持的拓扑结构"
    detail: "当前源设备和目标设备的类型组合不在支持范围内"
    action: "提示用户检查设备类型组合"

  ERR_MEDIA_MISMATCH:
    code: "E007"
    message: "介质类型不匹配"
    detail: "源端口介质({src_media})与目标端口介质({dst_media})不一致"
    action: "提示用户使用光电转换模块或选择匹配介质端口"

  ERR_SPEED_MISMATCH:
    code: "E008"
    message: "速率不匹配"
    detail: "源端口速率({src_speed})与目标端口速率({dst_speed})不一致"
    action: "提示用户确认是否支持降速或更换端口"
```

---

## 7. 端口选择算法汇总（Algorithm Reference）

```yaml
algorithms:
  SEQUENTIAL_SCAN:
    description: "从最小端口号开始顺序扫描，选中第一个满足条件的端口"
    use_in: ["A1源端", "B1"]
    parameters:
      start: 0
      direction: ASCENDING
      filter: "status==FREE && type_match && speed_match && media_match"

  PER_DEVICE_SEQUENTIAL:
    description: "对组内每台设备独立执行顺序扫描"
    use_in: ["A2源端", "A3源端"]
    parameters:
      per_device: true
      filter: "status==FREE && type_match"

  MIN_SLOT_MIN_PORT:
    description: "先选最小slot编号，再在该slot上选最小端口号"
    use_in: ["C1源端", "C2源端", "C3源端"]
    parameters:
      slot_order: ASCENDING
      port_order: ASCENDING
      filter: "status==FREE && type_match"

  ONE_PORT_PER_SLOT:
    description: "每个slot取1个端口，优先使用不同slot分散连接"
    use_in: ["A2目标端 - slot充足时"]
    parameters:
      distribution: SPREAD

  ROUND_ROBIN_ACROSS_SLOTS:
    description: "slot不足时按轮询方式复用slot端口"
    use_in: ["A2目标端 - slot不足时"]
    parameters:
      strategy: ROUND_ROBIN
      example: "slot1-p1 → slot2-p1 → slot1-p2 → slot2-p2 → ..."

  CROSS_CONNECT_MINIMAL:
    description: "源组和目标组交叉连接，保证每台设备至少1条链路"
    use_in: ["A3"]
    parameters:
      ensure_full_mesh: false
      min_links_per_device: 1

  CROSS_GROUP_CONNECT:
    description: "跨组连接，源组每台交换机连接目标组交换机"
    use_in: ["C3"]
    parameters:
      ensure_bidirectional: true

  RESERVED_PORT_INTERCONNECT:
    description: "使用保留端口（UPLINK/DOWNLINK最后2个口）做组内互联"
    use_in: ["D1"]
    parameters:
      reserved_count: 2  # 每类端口保留最后2个
      roles: [PEER_LINK, DAD]

  CROSS_INTERCONNECT_LAST_PORTS:
    description: "组间使用板卡尾部端口交叉互联"
    use_in: ["D2-auto"]
    parameters:
      port_offset_from_end: 2  # 每个板卡最后2个端口
```

---

## 8. 全局约束与优先级规则

```yaml
global_constraints:
  # ===== 优先级从高到低 =====

  P0_端口状态约束:
    - "OCCUPIED状态的端口不可被选中"
    - "RESERVED状态的端口（PEER_LINK/DAD）不可被选中"
    - "只有FREE状态的端口可参与连线"

  P1_类型匹配约束:
    - "10G交换机端口只能对接10G接口（服务器10G slot或交换机10G UPLINK）"
    - "1G交换机端口只能对接1G接口"
    - "25G/40G/100G同理，需严格匹配或确认支持降速"

  P2_介质匹配约束:
    - "光纤端口↔光纤端口"
    - "铜缆端口↔铜缆端口"
    - "不匹配时提示使用光电转换模块，但不自动连线"

  P3_角色约束:
    - "交换机→服务器/安全设备：源端角色=DOWNLINK"
    - "核心/汇聚→接入交换机：源端=DOWNLINK，目标端=UPLINK"
    - "BMC交换机→服务器：源端=BMC，目标端=IPMI/BMC口"
    - "组内互联：端口角色=PEER_LINK + DAD（自动保留）"

  P4_组连通性约束:
    - "设备组间连线时，确保源组每台设备至少连接1条到目标组的链路"
    - "目标组每台设备至少连接1条到源组的链路"
    - "组内互联（D1）的保留端口不参与组间连线"

  P5_端口唯一性约束:
    - "同一物理端口不可被重复分配给多条连线"
    - "连线建立后端口状态立即更新为OCCUPIED"

  P6_冗余建议（非强制）:
    - "关键链路建议双链路冗余（不同物理路径）"
    - "服务器建议双网卡分别连接不同交换机（A2场景）"
    - "核心层建议全互联或部分互联拓扑"
```

---

## 9. 端口选择决策流程（Port Selection Flowchart）

```
输入: 源设备S, 目标设备T, 模式(AUTO/MANUAL)
│
├─ MANUAL模式？
│   └─ YES → 展示FREE端口列表 → 用户选择 → 校验匹配 → 建立连线
│
└─ AUTO模式？
    │
    ├─ Step 1: 确定源端口角色
    │   ├─ S是核心/汇聚/接入交换机，T是下级设备 → 源=DOWNLINK
    │   ├─ S是BMC交换机 → 源=BMC
    │   └─ S是交换机，T是同组交换机 → 源=PEER_LINK/DAD保留口
    │
    ├─ Step 2: 确定目标端口角色
    │   ├─ T是接入交换机，S是上级 → 目标=UPLINK
    │   ├─ T是服务器/安全设备 → 目标=SERVER_NIC（按slot匹配）
    │   └─ T是同组交换机 → 目标=PEER_LINK/DAD保留口
    │
    ├─ Step 3: 端口类型匹配筛选
    │   ├─ 获取S的端口类型（10G/1G/25G/...）
    │   ├─ 获取T上相同类型的端口/slot列表
    │   └─ 无匹配 → ERR_NO_MATCHING_INTERFACE
    │
    ├─ Step 4: 执行端口选择算法
    │   ├─ S为单台 → SEQUENTIAL_SCAN (从port 0开始)
    │   ├─ S为组 → PER_DEVICE_SEQUENTIAL (每台独立扫描)
    │   ├─ S为核心/汇聚 → MIN_SLOT_MIN_PORT (最小slot最小端口)
    │   └─ 组内互联 → RESERVED_PORT_INTERCONNECT (最后2个端口)
    │
    ├─ Step 5: 介质与速率校验
    │   ├─ 介质匹配？(FIBER↔FIBER, COPPER↔COPPER)
    │   │   └─ NO → ERR_MEDIA_MISMATCH
    │   ├─ 速率匹配？或支持降速？
    │   │   └─ NO → ERR_SPEED_MISMATCH
    │   └─ 通过 → 继续
    │
    ├─ Step 6: 组连通性校验（若涉及设备组）
    │   ├─ 源组每台设备至少1条链路？
    │   │   └─ NO → 补充连线或 ERR_INSUFFICIENT_PORTS
    │   ├─ 目标组每台设备至少1条链路？
    │   │   └─ NO → 补充连线或 ERR_INSUFFICIENT_PORTS
    │   └─ 通过 → 继续
    │
    └─ Step 7: 建立连线
        ├─ 创建Link记录
        ├─ 端口状态 FREE → OCCUPIED
        └─ 返回 LinkResult
```

---

## 10. 场景速查表（Quick Reference）

| 场景ID | 源设备 | 目标设备 | 源端口角色 | 目标端口角色 | 自动算法 | 说明 |
|--------|--------|----------|-----------|-------------|---------|------|
| A1 | 单台接入交换机 | 单台服务器/安全设备 | DOWNLINK | SERVER_NIC | SEQUENTIAL_SCAN | 最基础场景 |
| A2 | 交换机组(N台) | 单台服务器/安全设备 | DOWNLINK | SERVER_NIC | PER_DEVICE + ROUND_ROBIN | slot复用逻辑 |
| A3 | 交换机组(N台) | 服务器组(M台) | DOWNLINK | SERVER_NIC | CROSS_CONNECT_MINIMAL | 组对组交叉 |
| B1 | BMC千兆交换机 | 服务器IPMI口 | BMC | BMC | SEQUENTIAL_SCAN | 带外管理 |
| C1 | 单台核心/汇聚 | 单台接入交换机 | DOWNLINK | UPLINK | MIN_SLOT_MIN_PORT | 上联 |
| C2 | 核心/汇聚组 | 单台接入交换机 | DOWNLINK | UPLINK | PER_DEVICE + SEQ_UPLINK | 多对一上联 |
| C3 | 核心/汇聚组 | 接入交换机组 | DOWNLINK | UPLINK | CROSS_GROUP_CONNECT | 组对组上联 |
| C4 | 核心/汇聚组 | 千兆接入交换机 | DOWNLINK | UPLINK | 继承C1-C3 | 万兆→千兆汇聚 |
| D1 | 同组交换机 | 同组交换机 | PEER_LINK/DAD | PEER_LINK/DAD | RESERVED_PORT | 堆叠/M-LAG互联 |
| D2 | 核心组A | 核心组B | DOWNLINK | UPLINK | CROSS_INTERCONNECT | 跨组互联 |

---

## 11. 补充设计：扩展场景（原文未覆盖）

### 11.1 安全设备旁挂/串接

```yaml
scenario: E1
name: "安全设备旁挂/串接部署"
description: "安全设备（防火墙/WAF/IDS）以旁挂或串接方式接入网络"

rules:
  bypass_mode:  # 旁挂模式
    logic: |
      1. 安全设备通过核心交换机的DOWNLINK端口接入
      2. 流量通过策略路由引流到安全设备
      3. 端口选择逻辑同场景A1/C1
    port_role: "交换机侧=DOWNLINK, 安全设备侧=SERVER_NIC"

  inline_mode:  # 串接模式
    logic: |
      1. 安全设备串联在核心交换机与接入交换机之间
      2. 核心交换机DOWNLINK → 安全设备IN口
      3. 安全设备OUT口 → 接入交换机UPLINK
      4. 需要2条连线，安全设备需有IN/OUT端口对
    port_role: "核心侧=DOWNLINK, 安全设备=IN/OUT, 接入侧=UPLINK"
    constraint: "串接模式下安全设备必须成对配置IN/OUT端口"
```

### 11.2 服务器多网卡Bond/聚合

```yaml
scenario: E2
name: "服务器多网卡Bond链路聚合"
description: "服务器通过多网卡做Bond，分别连接到不同交换机实现冗余"

rules:
  logic: |
    1. 服务器配置Bond模式（active-backup/LACP/802.3ad）
    2. Bond成员端口分别连接到不同物理交换机
    3. 端口选择逻辑同场景A2
    4. 额外约束：Bond成员端口必须分布在不同交换机上

  constraints:
    - rule: "Bond成员端口不可连接到同一台交换机"
    - rule: "LACP/802.3ad模式要求两端交换机配置一致"
    - rule: "建议active-backup模式用于跨交换机Bond"
```

### 11.3 光纤/铜缆介质适配

```yaml
scenario: E3
name: "介质适配场景"
description: "当源端口和目标端口介质不一致时的处理"

rules:
  logic: |
    1. 默认要求介质匹配（光纤↔光纤，铜缆↔铜缆）
    2. 若不匹配，检测是否安装光电转换模块（SFP/SFP+/QSFP）
    3. 若有转换模块 → 允许连线，标记 warning MEDIA_ADAPTER_USED
    4. 若无转换模块 → ERR_MEDIA_MISMATCH

  media_matrix:
    fiber_to_fiber: "直接连线"
    copper_to_copper: "直接连线"
    fiber_to_copper: "需光电转换模块"
    copper_to_fiber: "需光电转换模块"
```

### 11.4 速率降级场景

```yaml
scenario: E4
name: "速率降级连接"
description: "高速端口连接低速端口时的降速处理"

rules:
  logic: |
    1. 默认要求速率严格匹配
    2. 若源端口速率 > 目标端口速率：
       a. 检查源端口是否支持降速（如10G端口降速到1G）
       b. 支持降速 → 允许连线，标记 warning SPEED_DOWNGRADE
       c. 不支持 → ERR_SPEED_MISMATCH
    3. 若源端口速率 < 目标端口速率：
       a. 检查目标端口是否支持降速
       b. 同上处理

  speed_matrix:
    "10G_to_10G": "直接连线"
    "10G_to_1G":  "需源端口支持降速至1G"
    "25G_to_10G": "需源端口支持降速至10G"
    "40G_to_10G": "需使用分支线缆（40G→4×10G）"
    "100G_to_25G": "需使用分支线缆（100G→4×25G）"
    "1G_to_10G":  "需目标端口支持降速至1G"
```

### 11.5 级联扩展场景

```yaml
scenario: E5
name: "接入交换机级联扩展"
description: "接入交换机端口不足时，级联扩展接入交换机"

rules:
  logic: |
    1. 主接入交换机的DOWNLINK端口连接扩展交换机的UPLINK端口
    2. 端口选择逻辑：
       a. 主交换机：从最后一个FREE的DOWNLINK端口开始（避免与服务器连线冲突）
       b. 扩展交换机：从UPLINK最小端口开始
    3. 级联层级建议不超过2级

  constraints:
    - rule: "级联端口带宽不应成为瓶颈（建议≥上联带宽）"
    - rule: "级联交换机与主交换机需在同一VLAN"
    - rule: "级联层级 ≤ 2层"
```

---

## 12. 版本与维护

```yaml
version: "2.0"
date: "2026-08-12"
format: "AI-Structured YAML + Decision Tree"
engine_status: "frontend/src/utils/wiring 已按本文件实现场景路由 A1–D2（执行入口 applyWiringRule）"
changes:
  - "重构为结构化格式，新增数据模型定义"
  - "新增场景分类决策树（§1）"
  - "新增统一错误处理（§6）和算法汇总（§7）"
  - "新增全局约束优先级体系（§8）"
  - "新增端口选择决策流程图（§9）"
  - "新增场景速查表（§10）"
  - "补充5类扩展场景：安全设备旁挂、Bond聚合、介质适配、速率降级、级联扩展（§11）"
  - "统一自动/手动模式的逻辑描述"
```
