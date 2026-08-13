# Topology Scenarios - 拓扑场景

## 1. 支持的拓扑类型

### 1.1 三层架构 (Three-Tier)

┌─────────────────────────────────────────────────────────────┐
│ Core Layer │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│ │ Core 1 │━━━━│ Core 2 │━━━━│ Core 3 │━━━━│ Core 4 │ │
│ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ │
│ │ │ │ │ │
│ └─────────────┼─────────────┼─────────────┘ │
│ │ │ │
├─────────────────────┼─────────────┼─────────────────────────┤
│ Aggregation Layer │ │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│ │ Agg 1 │━━━━│ Agg 2 │━━━━│ Agg 3 │━━━━│ Agg 4 │ │
│ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ │
│ │ │ │ │ │
│ └─────────────┼─────────────┼─────────────┘ │
│ │ │ │
├─────────────────────┼─────────────┼─────────────────────────┤
│ Access Layer │ │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│ │ Acc 1 │━━━━│ Acc 2 │━━━━│ Acc 3 │━━━━│ Acc 4 │ │
│ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ │
│ │ │ │ │ │
│ └─────────────┼─────────────┼─────────────┘ │
│ │ │ │
├─────────────────────┼─────────────┼─────────────────────────┤
│ Server Layer │ │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│ │ Server │ │ Server │ │ Server │ │ Server │ │
│ └────────┘ └────────┘ └────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────┘

text

```
### 1.2 Spine-Leaf架构
```



┌─────────────────────────────────────────────────────────────┐
│ Spine Layer │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│ │ Spine1 │━━━━│ Spine2 │━━━━│ Spine3 │━━━━│ Spine4 │ │
│ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ │
│ │ │ │ │ │
│ ├─────────────┼─────────────┼─────────────┤ │
│ │ │ │ │ │
├───────┼─────────────┼─────────────┼─────────────┼──────────┤
│ │ │ │ │ │
│ ┌────┴───┐ ┌────┴───┐ ┌────┴───┐ ┌────┴───┐ │
│ │ Leaf 1 │ │ Leaf 2 │ │ Leaf 3 │ │ Leaf 4 │ │
│ └────┬───┘ └────┬───┘ └────┬───┘ └────┬───┘ │
│ │ │ │ │ │
│ └─────────────┼─────────────┼─────────────┘ │
│ │ │ │
│ Server Layer │ │
│ ┌────────┐ ┌────────┐ ┌────────┐ ┌────────┐ │
│ │ Server │ │ Server │ │ Server │ │ Server │ │
│ └────────┘ └────────┘ └────────┘ └────────┘ │
└─────────────────────────────────────────────────────────────┘

text

```
### 1.3 安全拓扑
```



┌─────────────┐
│ Internet │
└──────┬──────┘
│
┌──────┴──────┐
│ Router │
└──────┬──────┘
│
┌──────┴──────┐
│ Firewall │
└──────┬──────┘
│
┌──────┴──────┐
│ Load Balancer│
└──────┬──────┘
│
┌─────────────┼─────────────┐
│ │ │
┌────┴───┐ ┌────┴───┐ ┌────┴───┐
│ Server │ │ Server │ │ Server │
└────────┘ └────────┘ └────────┘

text

```
## 2. 拓扑场景实现

​```python
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
import uuid

@dataclass
class TopologyScenario:
    """拓扑场景"""
    id: str
    name: str
    type: str
    description: str
    devices: List[Device]
    connections: List[Connection]
    parameters: Dict[str, Any] = field(default_factory=dict)

class TopologyScenarioGenerator:
    """拓扑场景生成器"""
    
    async def generate_three_tier(self, 
                                  core_count: int = 2,
                                  agg_count: int = 4,
                                  access_count: int = 8) -> TopologyScenario:
        """生成三层架构场景"""
        devices = []
        connections = []
        
        # 创建Core层
        cores = [Device(
            id=f"core-{i}",
            name=f"Core-SW-{i+1}",
            role=DeviceRole.CORE_SWITCH,
            rack=f"RACK-{i//2+1}",
            status=DeviceStatus.ACTIVE
        ) for i in range(core_count)]
        devices.extend(cores)
        
        # 创建Aggregation层
        aggs = [Device(
            id=f"agg-{i}",
            name=f"Agg-SW-{i+1}",
            role=DeviceRole.AGGREGATION_SWITCH,
            rack=f"RACK-{i//2+1}",
            status=DeviceStatus.ACTIVE
        ) for i in range(agg_count)]
        devices.extend(aggs)
        
        # 创建Access层
        accesses = [Device(
            id=f"access-{i}",
            name=f"Access-SW-{i+1}",
            role=DeviceRole.ACCESS_SWITCH,
            rack=f"RACK-{i//4+1}",
            status=DeviceStatus.ACTIVE
        ) for i in range(access_count)]
        devices.extend(accesses)
        
        # 创建服务器
        servers = [Device(
            id=f"server-{i}",
            name=f"Server-{i+1}",
            role=DeviceRole.SERVER,
            rack=f"RACK-{(i//8)+1}",
            status=DeviceStatus.ACTIVE
        ) for i in range(access_count * 4)]
        devices.extend(servers)
        
        return TopologyScenario(
            id=str(uuid.uuid4()),
            name="Three-Tier Network",
            type="three_tier",
            description="Standard three-tier network architecture",
            devices=devices,
            connections=connections,
            parameters={
                'core_count': core_count,
                'agg_count': agg_count,
                'access_count': access_count,
                'server_count': len(servers)
            }
        )
    
    async def generate_spine_leaf(self,
                                  spine_count: int = 4,
                                  leaf_count: int = 8) -> TopologyScenario:
        """生成Spine-Leaf场景"""
        devices = []
        connections = []
        
        # 创建Spine层
        spines = [Device(
            id=f"spine-{i}",
            name=f"Spine-{i+1}",
            role=DeviceRole.SPINE_SWITCH,
            rack=f"RACK-{i//2+1}",
            status=DeviceStatus.ACTIVE
        ) for i in range(spine_count)]
        devices.extend(spines)
        
        # 创建Leaf层
        leafs = [Device(
            id=f"leaf-{i}",
            name=f"Leaf-{i+1}",
            role=DeviceRole.LEAF_SWITCH,
            rack=f"RACK-{i//2+1}",
            status=DeviceStatus.ACTIVE
        ) for i in range(leaf_count)]
        devices.extend(leafs)
        
        # 创建服务器
        servers = [Device(
            id=f"server-{i}",
            name=f"Server-{i+1}",
            role=DeviceRole.SERVER,
            rack=f"RACK-{(i//16)+1}",
            status=DeviceStatus.ACTIVE
        ) for i in range(leaf_count * 4)]
        devices.extend(servers)
        
        return TopologyScenario(
            id=str(uuid.uuid4()),
            name="Spine-Leaf Network",
            type="spine_leaf",
            description="Modern spine-leaf network architecture",
            devices=devices,
            connections=connections,
            parameters={
                'spine_count': spine_count,
                'leaf_count': leaf_count,
                'server_count': len(servers)
            }
        )
    
    async def generate_security_topology(self) -> TopologyScenario:
        """生成安全拓扑场景"""
        devices = []
        connections = []
        
        # 创建安全设备
        router = Device(
            id="router-1",
            name="Edge-Router",
            role=DeviceRole.ROUTER,
            rack="RACK-1",
            status=DeviceStatus.ACTIVE
        )
        devices.append(router)
        
        firewall = Device(
            id="firewall-1",
            name="Firewall",
            role=DeviceRole.FIREWALL,
            rack="RACK-1",
            status=DeviceStatus.ACTIVE
        )
        devices.append(firewall)
        
        load_balancer = Device(
            id="lb-1",
            name="Load-Balancer",
            role=DeviceRole.LOAD_BALANCER,
            rack="RACK-1",
            status=DeviceStatus.ACTIVE
        )
        devices.append(load_balancer)
        
        # 创建应用服务器
        servers = [Device(
            id=f"app-server-{i}",
            name=f"App-Server-{i+1}",
            role=DeviceRole.SERVER,
            rack=f"RACK-{i//4+1}",
            status=DeviceStatus.ACTIVE
        ) for i in range(8)]
        devices.extend(servers)
        
        return TopologyScenario(
            id=str(uuid.uuid4()),
            name="Security Topology",
            type="security",
            description="Security-focused network topology",
            devices=devices,
            connections=connections,
            parameters={
                'firewall_mode': 'ACTIVE_STANDBY',
                'load_balancer_mode': 'ACTIVE_ACTIVE'
            }
        )
```