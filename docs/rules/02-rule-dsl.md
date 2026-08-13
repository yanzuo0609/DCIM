# Rule DSL - 规则语言定义

## 1. 设计原则

1. **声明式**：规则描述"是什么"，而非"怎么做"
2. **可读性**：YAML格式，业务人员可理解
3. **可扩展**：新增规则类型无需修改解析器
4. **类型安全**：基于Pydantic验证

## 2. 规则基础结构

```yaml
# 规则文件基础结构
rule:
  id: "topology-core-to-aggregation-v1"
  name: "Core到Aggregation连接规则"
  version: "1.0.0"
  type: "topology"  # topology, redundancy, media, security, etc.
  priority: 100     # 优先级，数字越大越优先
  enabled: true
  
  # 规则描述
  description: |
    从Core交换机连接到Aggregation交换机
    要求至少2条链路提供冗余
  
  # 适用条件
  when:
    # 条件表达式
    topology_type: "three-tier"
    device_role_source: "CORE_SWITCH"
    device_role_target: "AGGREGATION_SWITCH"
  
  # 规则动作
  then:
    # 连接规格
    connection:
      count: "min(2, target_ports_available)"  # 表达式
      link_type: "UPLINK"
      
      # 每个连接的约束
      constraints:
        - speed: ">= 10000"  # 10G+
        - media: ["SMF", "MMF"]
        - redundancy:
            required: true
            diversity: ["DEVICE", "RACK"]
      
      # 评分配置
      scoring:
        same_rack: 30
        dac: 20
        shortest_path: 15
        speed_match: 10
  
  # 元数据
  metadata:
    author: "Network Team"
    created_at: "2024-01-15"
    tags: ["core", "aggregation", "redundant"]
```

## 3. 规则类型

### 3.1 Topology Rules

yaml

```
# topology/core-aggregation.yaml
rule:
  id: "topology-core-aggregation-v1"
  type: "topology"
  name: "Core到Aggregation连接"
  
  when:
    source_role: "CORE_SWITCH"
    target_role: "AGGREGATION_SWITCH"
    min_speed: 10000
    redundancy: true
    
  then:
    connection_count: "min(available_ports, 8)"
    link_type: "UPLINK"
    require_media: ["SMF", "MMF"]
    require_distance: "<= 300"
    scoring:
      same_rack: 30
      dac: 20
      shortest_path: 15
```



yaml

```
# topology/spine-leaf.yaml
rule:
  id: "topology-spine-leaf-v1"
  type: "topology"
  name: "Spine到Leaf连接"
  
  when:
    source_role: "SPINE_SWITCH"
    target_role: "LEAF_SWITCH"
    min_speed: 25000
    
  then:
    connection_count: "all_to_all"
    link_type: "UPLINK"
    require_media: ["SMF", "DAC"]
    scoring:
      same_rack: 25
      shortest_path: 20
      port_symmetry: 15
```



### 3.2 Redundancy Rules

yaml

```
# redundancy/dual-uplink.yaml
rule:
  id: "redundancy-dual-uplink-v1"
  type: "redundancy"
  name: "双上行冗余"
  
  when:
    device_role: "ACCESS_SWITCH"
    uplink_count: ">= 2"
    
  then:
    redundancy_type: "ACTIVE_ACTIVE"
    diversity_requirements:
      - type: "DEVICE"
        min_devices: 2
      - type: "RACK"
        min_racks: 2
    scoring:
      device_diversity: 20
      rack_diversity: 10
```



yaml

```
# redundancy/mlag.yaml
rule:
  id: "redundancy-mlag-v1"
  type: "mlag"
  name: "MLAG配置"
  
  when:
    domain_required: true
    device_count: 2
    
  then:
    require_peer_link: true
    peer_link_speed: ">= 40000"
    require_keepalive: true
    downstream_links: 4
    
  constraints:
    - peer_link_min_speed: "40000"
    - keepalive_vlan: 4094
    - mlag_vlan: 4093
```



### 3.3 Media Rules

yaml

```
# media/dac-rule.yaml
rule:
  id: "media-dac-v1"
  type: "media"
  name: "DAC线缆优先"
  
  when:
    distance: "<= 7"
    speed: ["10000", "25000", "40000"]
    
  then:
    preferred_cable: "DAC"
    scoring:
      cable_match: 20
    fallback: "AOC"
```



yaml

```
# media/fiber-rule.yaml
rule:
  id: "media-fiber-v1"
  type: "media"
  name: "光纤连接规则"
  
  when:
    distance: "> 7"
    speed: ">= 10000"
    
  then:
    preferred_cable: "SMF_PATCH"
    require_module: true
    module_form_factor: ["SFP28", "QSFP28"]
    scoring:
      module_compatibility: 20
```



### 3.4 Security Rules

yaml

```
# security/firewall-placement.yaml
rule:
  id: "security-firewall-placement-v1"
  type: "security"
  name: "防火墙位置规则"
  
  when:
    traffic_flow: "WAN_TO_INTERNAL"
    requires_inspection: true
    
  then:
    sequence: ["WAN", "ROUTER", "FIREWALL", "LOAD_BALANCER", "SERVER"]
    firewall_mode: "ACTIVE_STANDBY"
    zones:
      - name: "UNTRUST"
        ports: ["OUTSIDE"]
      - name: "TRUST"
        ports: ["INSIDE"]
```



### 3.5 Resource Allocation Rules

yaml

```
# allocation/port-reservation.yaml
rule:
  id: "allocation-port-reservation-v1"
  type: "allocation"
  name: "端口预留规则"
  
  when:
    device_role: "CORE_SWITCH"
    
  then:
    reserve_ports:
      - count: 4
        role: "PEER_LINK"
      - count: 2
        role: "KEEPALIVE"
    scoring:
      reserved_port: 20
```



## 4. 表达式语法

### 4.1 支持的运算符

yaml

```
# 比较运算符
speed: ">= 10000"
distance: "<= 300"
count: "> 2"
port_count: "== 48"

# 逻辑运算符
conditions:
  and:
    - speed: ">= 10000"
    - media: "SMF"
  or:
    - media: "SMF"
    - media: "MMF"

# 算术表达式
connection_count: "min(available_ports, 8)"
max_connections: "available_ports // 2"
```



### 4.2 内置函数

yaml

```
# 数学函数
count: "min(4, max(2, available_ports))"
total: "sum(port_speeds)"

# 集合函数
media: "intersect(supported_media, available_media)"
ports: "filter(ports, speed >= 10000)"

# 条件函数
scoring: "if(redundant, 30, 0)"
```



### 4.3 变量引用

yaml

```
# 设备变量
device:
  - id: "${source.id}"
  - role: "${source.role}"
  - rack: "${source.rack}"

# 端口变量
port:
  - speed: "${port.speed}"
  - status: "${port.status}"

# 环境变量
environment:
  - site: "${env.SITE}"
  - datacenter: "${env.DATACENTER}"
```



## 5. 规则验证模式

python

```
from pydantic import BaseModel, Field, validator
from typing import List, Optional, Dict, Any, Union
from enum import Enum

class RuleType(str, Enum):
    TOPOLOGY = "topology"
    REDUNDANCY = "redundancy"
    MLAG = "mlag"
    MEDIA = "media"
    MODULE = "module"
    CABLE = "cable"
    SECURITY = "security"
    ALLOCATION = "allocation"
    VALIDATION = "validation"
    OPTIMIZATION = "optimization"

class WhenCondition(BaseModel):
    """条件表达式"""
    # 比较
    eq: Optional[Dict[str, Any]] = None
    ne: Optional[Dict[str, Any]] = None
    gt: Optional[Dict[str, Any]] = None
    gte: Optional[Dict[str, Any]] = None
    lt: Optional[Dict[str, Any]] = None
    lte: Optional[Dict[str, Any]] = None
    contains: Optional[Dict[str, Any]] = None
    
    # 逻辑
    and_: Optional[List['WhenCondition']] = Field(None, alias="and")
    or_: Optional[List['WhenCondition']] = Field(None, alias="or")
    not_: Optional['WhenCondition'] = Field(None, alias="not")
    
    # 函数
    exists: Optional[str] = None
    matches: Optional[Dict[str, str]] = None
    
    class Config:
        extra = "allow"

class ScoringConfig(BaseModel):
    """评分配置"""
    same_rack: Optional[int] = 0
    same_device: Optional[int] = 0
    dac: Optional[int] = 0
    aoc: Optional[int] = 0
    shortest_path: Optional[int] = 0
    speed_match: Optional[int] = 0
    port_role_match: Optional[int] = 0
    reserved_port: Optional[int] = 0
    device_diversity: Optional[int] = 0
    rack_diversity: Optional[int] = 0
    path_diversity: Optional[int] = 0
    port_symmetry: Optional[int] = 0
    module_compatibility: Optional[int] = 0
    cable_match: Optional[int] = 0
    
    # 自定义评分
    custom: Dict[str, int] = Field(default_factory=dict)

class Rule(BaseModel):
    id: str = Field(..., description="规则唯一标识")
    name: str = Field(..., description="规则名称")
    version: str = Field(default="1.0.0", description="版本")
    type: RuleType = Field(..., description="规则类型")
    
    # 优先级
    priority: int = Field(default=0, description="优先级")
    enabled: bool = Field(default=True, description="是否启用")
    
    # 条件
    when: Dict[str, Any] = Field(..., description="触发条件")
    
    # 动作
    then: Dict[str, Any] = Field(..., description="执行动作")
    
    # 评分
    scoring: Optional[ScoringConfig] = Field(None, description="评分配置")
    
    # 约束
    constraints: List[Dict[str, Any]] = Field(default_factory=list, description="约束列表")
    
    # 冲突解决
    conflict_resolution: Optional[str] = Field(None, description="冲突解决策略")
    conflict_priority: Optional[int] = Field(None, description="冲突优先级")
    
    # 元数据
    description: Optional[str] = Field(None, description="规则描述")
    tags: List[str] = Field(default_factory=list, description="标签")
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    # 时间
    effective_from: Optional[datetime] = None
    effective_to: Optional[datetime] = None
    
    @validator('id')
    def validate_id(cls, v):
        if not re.match(r'^[a-z][a-z0-9-]*$', v):
            raise ValueError('ID must be lowercase alphanumeric with hyphens')
        return v

class RuleBundle(BaseModel):
    """规则包"""
    version: str = Field(..., description="规则包版本")
    rules: List[Rule] = Field(..., description="规则列表")
    
    # 元数据
    name: Optional[str] = None
    description: Optional[str] = None
    author: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.now)
```



## 6. DSL解析器

python

```
from typing import Dict, Any, List, Optional
import yaml
import json
from pathlib import Path

class DSLParser:
    """DSL解析器"""
    
    def __init__(self, schema_path: Optional[Path] = None):
        self.schema = self._load_schema(schema_path)
    
    def parse_file(self, file_path: Path) -> Rule:
        """解析规则文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return self.parse_dict(data)
    
    def parse_dict(self, data: Dict[str, Any]) -> Rule:
        """解析字典为规则对象"""
        if 'rule' not in data:
            raise ValueError("Invalid rule format: missing 'rule' key")
        
        rule_data = data['rule']
        return Rule(**rule_data)
    
    def parse_bundle(self, directory: Path) -> RuleBundle:
        """解析目录中的所有规则"""
        rules = []
        for file_path in directory.glob("**/*.yaml"):
            try:
                rule = self.parse_file(file_path)
                rules.append(rule)
            except Exception as e:
                raise ValueError(f"Error parsing {file_path}: {e}")
        
        return RuleBundle(version="1.0.0", rules=rules)
    
    def validate(self, rule: Rule) -> bool:
        """验证规则"""
        # 验证条件表达式
        self._validate_conditions(rule.when)
        # 验证动作
        self._validate_actions(rule.then)
        # 验证评分
        if rule.scoring:
            self._validate_scoring(rule.scoring)
        return True
    
    def _validate_conditions(self, conditions: Dict[str, Any]) -> bool:
        """验证条件表达式"""
        for key, value in conditions.items():
            if key in ['and', 'or', 'not']:
                if isinstance(value, list):
                    for cond in value:
                        self._validate_conditions(cond)
                else:
                    self._validate_conditions(value)
        return True
    
    def _validate_actions(self, actions: Dict[str, Any]) -> bool:
        """验证动作"""
        # 检查必需字段
        required = ['connection']
        for req in required:
            if req not in actions:
                raise ValueError(f"Missing required action: {req}")
        return True
    
    def _validate_scoring(self, scoring: ScoringConfig) -> bool:
        """验证评分配置"""
        # 检查评分值在合理范围
        for field, value in scoring.dict().items():
            if isinstance(value, int) and value < 0:
                raise ValueError(f"Score must be non-negative: {field}={value}")
        return True
```



## 7. 规则示例集

### 7.1 完整的三层架构规则

yaml

```
# 完整的三层架构规则包
version: "1.0.0"
name: "Three-Tier Network Rules"
description: "三层网络架构的完整规则集"

rules:
  # Core到Aggregation
  - id: "topology-core-to-aggregation-v1"
    type: "topology"
    name: "Core到Aggregation连接"
    when:
      source_role: "CORE_SWITCH"
      target_role: "AGGREGATION_SWITCH"
    then:
      connection_count: "min(available_ports, 8)"
      link_type: "UPLINK"
      constraints:
        - speed: ">= 10000"
        - media: ["SMF", "MMF"]

  # Aggregation到Access
  - id: "topology-aggregation-to-access-v1"
    type: "topology"
    name: "Aggregation到Access连接"
    when:
      source_role: "AGGREGATION_SWITCH"
      target_role: "ACCESS_SWITCH"
    then:
      connection_count: "min(available_ports, 4)"
      link_type: "DOWNLINK"
      constraints:
        - speed: ">= 1000"
        - media: ["SMF", "MMF", "CAT6A"]
```



### 7.2 Spine-Leaf规则

yaml

```
version: "1.0.0"
name: "Spine-Leaf Network Rules"

rules:
  - id: "topology-spine-to-leaf-v1"
    type: "topology"
    name: "Spine到Leaf连接"
    priority: 200
    when:
      source_role: "SPINE_SWITCH"
      target_role: "LEAF_SWITCH"
    then:
      connection_count: "all_to_all"
      link_type: "UPLINK"
      constraints:
        - speed: ">= 40000"
        - media: ["SMF", "DAC"]
      scoring:
        same_rack: 25
        shortest_path: 20
        port_symmetry: 15
```