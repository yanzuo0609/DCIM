# Domain Model - 领域模型

## 1. 核心实体

### 1.1 Device（设备）

```python
from typing import List, Optional, Dict, Any
from enum import Enum
from datetime import datetime
from pydantic import BaseModel, Field

class DeviceRole(str, Enum):
    # 交换机
    CORE_SWITCH = "CORE_SWITCH"
    AGGREGATION_SWITCH = "AGGREGATION_SWITCH"
    ACCESS_SWITCH = "ACCESS_SWITCH"
    SPINE_SWITCH = "SPINE_SWITCH"
    LEAF_SWITCH = "LEAF_SWITCH"
    
    # 路由和安全
    ROUTER = "ROUTER"
    FIREWALL = "FIREWALL"
    WAF = "WAF"
    IPS = "IPS"
    IDS = "IDS"
    LOAD_BALANCER = "LOAD_BALANCER"
    ANTI_DDOS = "ANTI_DDOS"
    
    # 服务器和存储
    SERVER = "SERVER"
    STORAGE = "STORAGE"
    SAN_SWITCH = "SAN_SWITCH"
    
    # 基础设施
    PATCH_PANEL = "PATCH_PANEL"
    ODF = "ODF"
    PDU = "PDU"
    
    # 扩展
    VPN = "VPN"
    SDN = "SDN"
    DPU = "DPU"
    NIC = "NIC"
    AP = "AP"
    WIRELESS_CONTROLLER = "WIRELESS_CONTROLLER"
    OPTICAL_DEVICE = "OPTICAL_DEVICE"
    WDM = "WDM"

class DeviceStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    MAINTENANCE = "MAINTENANCE"
    PLANNED = "PLANNED"
    DECOMMISSIONED = "DECOMMISSIONED"

class Device(BaseModel):
    id: str = Field(..., description="设备唯一标识")
    name: str = Field(..., description="设备名称")
    type: str = Field(..., description="设备型号")
    role: DeviceRole = Field(..., description="设备角色")
    vendor: Optional[str] = Field(None, description="厂商")
    model: Optional[str] = Field(None, description="型号")
    
    # 位置信息
    rack: Optional[str] = Field(None, description="机柜编号")
    rack_unit: Optional[int] = Field(None, description="机柜U位")
    position: Optional[str] = Field(None, description="位置描述")
    site: Optional[str] = Field(None, description="站点/机房")
    room: Optional[str] = Field(None, description="房间")
    
    # 能力
    capabilities: Dict[str, Any] = Field(default_factory=dict, description="设备能力")
    
    # 冗余
    redundancy_group: Optional[str] = Field(None, description="冗余组ID")
    redundancy_role: Optional[str] = Field(None, description="冗余角色: PRIMARY/SECONDARY/STANDALONE")
    
    # 状态
    status: DeviceStatus = Field(default=DeviceStatus.ACTIVE, description="设备状态")
    
    # 关联
    ports: List['Port'] = Field(default_factory=list, description="端口列表")
    modules: List['Module'] = Field(default_factory=list, description="模块列表")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }
```

### 1.2 Port（端口）

```python
class PortType(str, Enum):
    ETHERNET = "ETHERNET"
    FIBRE_CHANNEL = "FIBRE_CHANNEL"
    CONSOLE = "CONSOLE"
    MANAGEMENT = "MANAGEMENT"
    POWER = "POWER"
    STACK = "STACK"

class PortRole(str, Enum):
    # 拓扑角色
    UPLINK = "UPLINK"
    DOWNLINK = "DOWNLINK"
    PEER_LINK = "PEER_LINK"
    KEEPALIVE = "KEEPALIVE"
    STACK = "STACK"
    HA = "HA"
    SYNC = "SYNC"
    
    # 管理角色
    MANAGEMENT = "MANAGEMENT"
    OOB = "OOB"  # Out-of-Band
    
    # 安全角色
    INSIDE = "INSIDE"
    OUTSIDE = "OUTSIDE"
    DMZ = "DMZ"
    
    # 功能角色
    SERVER = "SERVER"
    STORAGE = "STORAGE"
    SAN = "SAN"
    ISL = "ISL"  # Inter-Switch Link
    WAN = "WAN"
    
    # 通用
    UNKNOWN = "UNKNOWN"

class PortStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    ALLOCATED = "ALLOCATED"
    LOCKED = "LOCKED"
    FAILED = "FAILED"
    DOWN = "DOWN"

class BreakoutMode(str, Enum):
    NONE = "NONE"
    FOUR_X_25G = "4x25G"
    FOUR_X_10G = "4x10G"
    TWO_X_50G = "2x50G"
    EIGHT_X_25G = "8x25G"

class Port(BaseModel):
    id: str = Field(..., description="端口唯一标识")
    name: str = Field(..., description="端口名称，如 Eth1/1")
    device_id: str = Field(..., description="所属设备ID")
    
    # 类型和角色
    type: PortType = Field(default=PortType.ETHERNET)
    role: PortRole = Field(default=PortRole.UNKNOWN)
    
    # 速率
    speed: int = Field(..., description="当前速率 (Mbps)")
    supported_speeds: List[int] = Field(default_factory=list, description="支持的速率列表 (Mbps)")
    auto_negotiate: bool = Field(default=True, description="是否自动协商")
    
    # 物理特性
    connector: Optional[str] = Field(None, description="接口类型: RJ45, LC, MPO, etc.")
    media: Optional[str] = Field(None, description="介质类型: Copper, Fiber, etc.")
    wavelength: Optional[int] = Field(None, description="波长 (nm)")
    fiber_count: Optional[int] = Field(None, description="光纤芯数")
    
    # 模块
    module_id: Optional[str] = Field(None, description="关联的模块ID")
    module_required: bool = Field(default=True, description="是否需要模块")
    
    # 状态
    status: PortStatus = Field(default=PortStatus.AVAILABLE)
    reserved_by: Optional[str] = Field(None, description="预留者ID")
    allocated_to: Optional[str] = Field(None, description="分配给连接ID")
    
    # Breakout
    breakout_mode: BreakoutMode = Field(default=BreakoutMode.NONE)
    breakout_ports: List[str] = Field(default_factory=list, description="Breakout子端口ID")
    parent_port_id: Optional[str] = Field(None, description="父端口ID（如果是breakout子端口）")
    
    # 物理位置
    rack: Optional[str] = Field(None, description="机柜位置")
    panel_slot: Optional[str] = Field(None, description="面板槽位")
    port_index: Optional[int] = Field(None, description="端口索引")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 1.3 Module（光模块/收发器）

```python
class ModuleFormFactor(str, Enum):
    SFP = "SFP"
    SFP_PLUS = "SFP+"
    SFP28 = "SFP28"
    QSFP = "QSFP"
    QSFP_PLUS = "QSFP+"
    QSFP28 = "QSFP28"
    QSFP_DD = "QSFP-DD"
    OSFP = "OSFP"
    CFP = "CFP"
    CFP2 = "CFP2"
    CFP4 = "CFP4"
    XFP = "XFP"
    X2 = "X2"
    GBIC = "GBIC"
    SFF = "SFF"
    SFF_8482 = "SFF-8482"

class ModuleMedia(str, Enum):
    COPPER = "COPPER"
    SMF = "SMF"  # Single Mode Fiber
    MMF = "MMF"  # Multi Mode Fiber
    DAC = "DAC"  # Direct Attach Copper
    AOC = "AOC"  # Active Optical Cable

class ModuleProtocol(str, Enum):
    ETHERNET = "ETHERNET"
    FIBRE_CHANNEL = "FIBRE_CHANNEL"
    INFINIBAND = "INFINIBAND"
    SONET = "SONET"
    SDH = "SDH"

class ModuleStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    ALLOCATED = "ALLOCATED"
    FAILED = "FAILED"
    INCOMPATIBLE = "INCOMPATIBLE"

class Module(BaseModel):
    id: str = Field(..., description="模块唯一标识")
    part_number: str = Field(..., description="部件号")
    vendor: Optional[str] = Field(None, description="厂商")
    
    # 规格
    form_factor: ModuleFormFactor = Field(..., description="封装类型")
    speed: int = Field(..., description="速率 (Mbps)")
    media: ModuleMedia = Field(..., description="介质类型")
    protocol: ModuleProtocol = Field(default=ModuleProtocol.ETHERNET)
    
    # 光纤参数
    wavelength: Optional[int] = Field(None, description="波长 (nm)")
    wavelength_range: Optional[str] = Field(None, description="波长范围")
    fiber_count: Optional[int] = Field(None, description="光纤芯数")
    connector: Optional[str] = Field(None, description="连接器类型")
    
    # 距离
    max_distance_km: float = Field(..., description="最大传输距离 (km)")
    
    # 兼容性
    compatible_devices: List[str] = Field(default_factory=list, description="兼容设备型号列表")
    compatible_ports: List[str] = Field(default_factory=list, description="兼容端口类型列表")
    
    # 状态
    status: ModuleStatus = Field(default=ModuleStatus.AVAILABLE)
    allocated_to: Optional[str] = Field(None, description="分配给连接ID")
    
    # 温度范围
    operating_temp_min: Optional[float] = Field(None, description="最低工作温度 (°C)")
    operating_temp_max: Optional[float] = Field(None, description="最高工作温度 (°C)")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
```

### 1.4 Cable（线缆）

```python
class CableType(str, Enum):
    DAC = "DAC"              # Direct Attach Copper
    AOC = "AOC"              # Active Optical Cable
    SMF_PATCH = "SMF_PATCH"  # Single Mode Fiber Patch
    MMF_PATCH = "MMF_PATCH"  # Multi Mode Fiber Patch
    CAT6 = "CAT6"
    CAT6A = "CAT6A"
    CAT7 = "CAT7"
    CAT8 = "CAT8"
    MPO_SMF = "MPO_SMF"
    MPO_MMF = "MPO_MMF"
    COPPER_TWINAX = "COPPER_TWINAX"
    FIBER_RIBON = "FIBER_RIBON"
    FIBER_LOOSE = "FIBER_LOOSE"

class CableConnector(str, Enum):
    LC = "LC"
    SC = "SC"
    ST = "ST"
    FC = "FC"
    MPO = "MPO"
    MTP = "MTP"
    RJ45 = "RJ45"
    SFP = "SFP"
    QSFP = "QSFP"
    SN = "SN"
    MDC = "MDC"

class CablePolarity(str, Enum):
    A = "A"  # Standard
    B = "B"  # Cross
    C = "C"  # Pair-wise

class CableStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    ALLOCATED = "ALLOCATED"
    FAILED = "FAILED"

class Cable(BaseModel):
    id: str = Field(..., description="线缆唯一标识")
    part_number: str = Field(..., description="部件号")
    vendor: Optional[str] = Field(None, description="厂商")
    
    # 类型
    type: CableType = Field(..., description="线缆类型")
    connector_a: CableConnector = Field(..., description="A端连接器")
    connector_b: CableConnector = Field(..., description="B端连接器")
    
    # 规格
    speed: int = Field(..., description="支持的速率 (Mbps)")
    length_m: float = Field(..., description="长度 (米)")
    max_distance_m: Optional[float] = Field(None, description="最大传输距离 (米)")
    fiber_count: Optional[int] = Field(None, description="光纤芯数 (如适用)")
    
    # 极性（光纤）
    polarity: Optional[CablePolarity] = Field(None, description="极性")
    
    # 介质
    media: ModuleMedia = Field(..., description="介质类型")
    
    # 颜色
    color: Optional[str] = Field(None, description="颜色 (用于标识)")
    
    # 状态
    status: CableStatus = Field(default=CableStatus.AVAILABLE)
    allocated_to: Optional[str] = Field(None, description="分配给连接ID")
    
    # 物理路径
    path: Optional[List[str]] = Field(None, description="物理路径节点列表")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
```

### 1.5 Connection（连接）

```python
class ConnectionType(str, Enum):
    PHYSICAL = "PHYSICAL"
    LOGICAL = "LOGICAL"
    VIRTUAL = "VIRTUAL"

class LinkType(str, Enum):
    UPLINK = "UPLINK"
    DOWNLINK = "DOWNLINK"
    PEER_LINK = "PEER_LINK"
    KEEPALIVE = "KEEPALIVE"
    HA = "HA"
    STACK = "STACK"
    SYNC = "SYNC"
    TRUNK = "TRUNK"
    ACCESS = "ACCESS"
    WAN = "WAN"
    SAN = "SAN"
    ISL = "ISL"

class ConnectionStatus(str, Enum):
    DRAFT = "DRAFT"
    PROPOSED = "PROPOSED"
    APPROVED = "APPROVED"
    EXECUTED = "EXECUTED"
    REJECTED = "REJECTED"
    FAILED = "FAILED"

class ConnectionEnd(BaseModel):
    """连接端点"""
    device_id: str = Field(..., description="设备ID")
    device_name: str = Field(..., description="设备名称")
    port_id: str = Field(..., description="端口ID")
    port_name: str = Field(..., description="端口名称")
    module_id: Optional[str] = Field(None, description="模块ID")
    module_part_number: Optional[str] = Field(None, description="模块部件号")

class ConnectionPath(BaseModel):
    """物理路径"""
    nodes: List[Dict[str, Any]] = Field(default_factory=list, description="路径节点")
    total_length_m: Optional[float] = Field(None, description="总长度 (米)")
    hops: int = Field(default=0, description="跳数")

class Connection(BaseModel):
    id: str = Field(..., description="连接唯一标识")
    name: Optional[str] = Field(None, description="连接名称")
    
    # 端点
    source: ConnectionEnd = Field(..., description="源端点")
    destination: ConnectionEnd = Field(..., description="目标端点")
    
    # 线缆
    cable_id: Optional[str] = Field(None, description="线缆ID")
    cable: Optional[Cable] = Field(None, description="线缆对象")
    
    # 类型
    type: ConnectionType = Field(default=ConnectionType.PHYSICAL)
    link_type: LinkType = Field(..., description="链路类型")
    
    # 路径
    path: Optional[ConnectionPath] = Field(None, description="物理路径")
    
    # 冗余
    redundancy_group: Optional[str] = Field(None, description="冗余组ID")
    redundancy_index: Optional[int] = Field(None, description="冗余组内索引")
    
    # 规则
    rule_id: Optional[str] = Field(None, description="触发的规则ID")
    rule_name: Optional[str] = Field(None, description="触发的规则名称")
    
    # 评分
    score: Optional[float] = Field(None, description="总分")
    score_breakdown: Dict[str, float] = Field(default_factory=dict, description="评分明细")
    
    # 验证
    validated: bool = Field(default=False, description="是否验证通过")
    validation_errors: List[str] = Field(default_factory=list, description="验证错误")
    validation_warnings: List[str] = Field(default_factory=list, description="验证警告")
    
    # 解释
    explanation: Optional[str] = Field(None, description="决策解释")
    
    # 状态
    status: ConnectionStatus = Field(default=ConnectionStatus.DRAFT)
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 1.6 RedundancyGroup（冗余组）

```python
class RedundancyType(str, Enum):
    ACTIVE_ACTIVE = "ACTIVE_ACTIVE"
    ACTIVE_STANDBY = "ACTIVE_STANDBY"
    N_1 = "N+1"
    N_N = "N+N"
    MLAG = "MLAG"
    MC_LAG = "MC-LAG"
    STACK = "STACK"

class RedundancyDiversity(str, Enum):
    DEVICE = "DEVICE"
    PORT = "PORT"
    RACK = "RACK"
    PATH = "PATH"
    FAILURE_DOMAIN = "FAILURE_DOMAIN"
    POWER = "POWER"
    FABRIC = "FABRIC"

class RedundancyGroup(BaseModel):
    id: str = Field(..., description="冗余组唯一标识")
    name: str = Field(..., description="冗余组名称")
    
    type: RedundancyType = Field(..., description="冗余类型")
    diversity: List[RedundancyDiversity] = Field(default_factory=list, description="多样性要求")
    
    # 成员
    devices: List[str] = Field(default_factory=list, description="设备ID列表")
    connections: List[str] = Field(default_factory=list, description="连接ID列表")
    
    # 配置
    min_active: int = Field(default=1, description="最小活动数量")
    max_active: int = Field(default=2, description="最大活动数量")
    
    # 故障域
    failure_domain_id: Optional[str] = Field(None, description="故障域ID")
    
    # 状态
    status: str = Field(default="ACTIVE")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 1.7 MLAGDomain（MLAG域）

```python
class MLAGDomain(BaseModel):
    id: str = Field(..., description="MLAG域唯一标识")
    name: str = Field(..., description="MLAG域名称")
    
    # 成员设备
    device_a_id: str = Field(..., description="设备A ID")
    device_b_id: str = Field(..., description="设备B ID")
    
    # 链路
    peer_link_id: Optional[str] = Field(None, description="Peer-Link连接ID")
    keepalive_link_id: Optional[str] = Field(None, description="Keepalive连接ID")
    member_links: List[str] = Field(default_factory=list, description="成员链路连接ID列表")
    
    # 配置
    peer_link_parameters: Dict[str, Any] = Field(default_factory=dict)
    keepalive_parameters: Dict[str, Any] = Field(default_factory=dict)
    mlag_parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # 状态
    status: str = Field(default="ACTIVE")
    health: str = Field(default="HEALTHY")
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
```

### 1.8 PatchPanel / ODF（配线架/光配架）

```python
class PatchPanelType(str, Enum):
    COPPER = "COPPER"
    FIBER = "FIBER"
    HYBRID = "HYBRID"

class PatchPanelPort(BaseModel):
    id: str = Field(..., description="端口唯一标识")
    panel_id: str = Field(..., description="配线架ID")
    front_port: str = Field(..., description="前端端口")
    rear_port: str = Field(..., description="后端端口")
    status: PortStatus = Field(default=PortStatus.AVAILABLE)
    connected_to: Optional[str] = Field(None, description="连接到的端口ID")

class PatchPanel(BaseModel):
    id: str = Field(..., description="配线架唯一标识")
    name: str = Field(..., description="配线架名称")
    type: PatchPanelType = Field(..., description="配线架类型")
    
    # 物理位置
    rack: str = Field(..., description="机柜编号")
    rack_unit: int = Field(..., description="机柜U位")
    
    # 端口
    ports: List[PatchPanelPort] = Field(default_factory=list, description="端口列表")
    port_count: int = Field(..., description="端口数量")
    
    # 厂商
    vendor: Optional[str] = Field(None, description="厂商")
    model: Optional[str] = Field(None, description="型号")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)

class ODF(BaseModel):
    """Optical Distribution Frame"""
    id: str = Field(..., description="ODF唯一标识")
    name: str = Field(..., description="ODF名称")
    
    # 物理位置
    rack: str = Field(..., description="机柜编号")
    rack_unit: int = Field(..., description="机柜U位")
    
    # 端口
    ports: List[PatchPanelPort] = Field(default_factory=list, description="端口列表")
    fiber_count: int = Field(..., description="光纤芯数")
    
    # 类型
    type: str = Field(default="STANDARD", description="ODF类型")
    
    # 元数据
    metadata: Dict[str, Any] = Field(default_factory=dict)
```

### 1.9 Topology（拓扑）

```python
class TopologyNode(BaseModel):
    device_id: str = Field(..., description="设备ID")
    role: DeviceRole = Field(..., description="设备角色")
    position: Optional[Tuple[int, int]] = Field(None, description="图形位置 (x, y)")

class TopologyEdge(BaseModel):
    source: str = Field(..., description="源设备ID")
    target: str = Field(..., description="目标设备ID")
    link_type: LinkType = Field(..., description="链路类型")
    count: int = Field(default=1, description="链路数量")

class Topology(BaseModel):
    id: str = Field(..., description="拓扑唯一标识")
    name: str = Field(..., description="拓扑名称")
    type: str = Field(..., description="拓扑类型: THREE_TIER, SPINE_LEAF, etc.")
    
    nodes: List[TopologyNode] = Field(default_factory=list)
    edges: List[TopologyEdge] = Field(default_factory=list)
    
    # 参数
    parameters: Dict[str, Any] = Field(default_factory=dict)
    
    # 元数据
    created_at: datetime = Field(default_factory=datetime.now)
```

## 2. 领域关系图

text

```text
Device (1) ──────< (N) Port
    │                   │
    │                   │ (0-1)
    │                   ▼
    │                Module
    │                   │
    │                   │ (0-1)
    │                   ▼
    └──────< (N) Connection ────> (1) Cable
                        │
                        │ (0-1)
                        ▼
                  PatchPanel/ODF
                        │
                        │ (N)
                        ▼
                  Physical Path

Device (N) ──────> (1) RedundancyGroup
    │
    └──────> (1) MLAGDomain

Topology (1) ──────> (N) Device
    │
    └──────> (N) Connection
```

## 3. 状态机

### 3.1 Port状态流转

text

```
AVAILABLE → RESERVED → ALLOCATED → LOCKED
    ↑          ↓           ↓
    └──────────┴───────────┘
    (从RESERVED/ALLOCATED可回到AVAILABLE)
    (任何状态可转为FAILED)
```

### 3.2 Connection状态流转

text

```
DRAFT → PROPOSED → APPROVED → EXECUTED
   ↓        ↓          ↓
   └────────┴──────────┘
   (任何状态可转为REJECTED或FAILED)
```



## 4. 事件模型

python

```python
class DomainEvent(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    type: str = Field(..., description="事件类型")
    aggregate_id: str = Field(..., description="聚合根ID")
    aggregate_type: str = Field(..., description="聚合根类型")
    data: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    user_id: Optional[str] = Field(None, description="操作用户ID")
```



## 5. 仓储接口

python

```python
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

class IDeviceRepository(ABC):
    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[Device]: ...
    @abstractmethod
    async def find_by_ids(self, ids: List[str]) -> List[Device]: ...
    @abstractmethod
    async def find_by_role(self, role: DeviceRole) -> List[Device]: ...
    @abstractmethod
    async def find_by_rack(self, rack: str) -> List[Device]: ...
    @abstractmethod
    async def find_by_redundancy_group(self, group_id: str) -> List[Device]: ...
    @abstractmethod
    async def save(self, device: Device) -> Device: ...
    @abstractmethod
    async def delete(self, id: str) -> bool: ...

class IPortRepository(ABC):
    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[Port]: ...
    @abstractmethod
    async def find_by_device(self, device_id: str) -> List[Port]: ...
    @abstractmethod
    async def find_available_by_device(self, device_id: str) -> List[Port]: ...
    @abstractmethod
    async def save(self, port: Port) -> Port: ...
    @abstractmethod
    async def allocate(self, id: str, connection_id: str) -> bool: ...
    @abstractmethod
    async def release(self, id: str) -> bool: ...

class IConnectionRepository(ABC):
    @abstractmethod
    async def find_by_id(self, id: str) -> Optional[Connection]: ...
    @abstractmethod
    async def find_by_device(self, device_id: str) -> List[Connection]: ...
    @abstractmethod
    async def find_by_redundancy_group(self, group_id: str) -> List[Connection]: ...
    @abstractmethod
    async def save(self, connection: Connection) -> Connection: ...
    @abstractmethod
    async def delete(self, id: str) -> bool: ...
```