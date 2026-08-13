# Redundancy Model - 冗余模型

## 1. 冗余类型

| 类型 | 说明 | 适用场景 |
|------|------|----------|
| Single Uplink | 单上行 | 非关键业务 |
| Dual Uplink | 双上行 | 关键业务 |
| Multi-Uplink | 多上行 | 高可用要求 |
| Device Diversity | 设备多样性 | 设备级冗余 |
| Rack Diversity | 机柜多样性 | 机柜级冗余 |
| Path Diversity | 路径多样性 | 路径级冗余 |
| Failure Domain | 故障域隔离 | 故障隔离 |

## 2. 冗余模型实现

```python
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid

class RedundancyLevel(str, Enum):
    NONE = "none"
    SINGLE = "single"
    DUAL = "dual"
    MULTI = "multi"
    FULL = "full"

class DiversityType(str, Enum):
    DEVICE = "device"
    PORT = "port"
    RACK = "rack"
    PATH = "path"
    POWER = "power"
    FABRIC = "fabric"
    FAILURE_DOMAIN = "failure_domain"

@dataclass
class RedundancyRequirement:
    """冗余要求"""
    level: RedundancyLevel
    diversity: List[DiversityType]
    min_connections: int
    max_connections: Optional[int] = None
    failure_domain_id: Optional[str] = None

@dataclass
class RedundancyGroup:
    """冗余组"""
    id: str
    name: str
    type: str
    devices: List[str]
    connections: List[str]
    requirements: RedundancyRequirement
    status: str = "ACTIVE"

class RedundancyModel:
    """冗余模型"""
    
    def __init__(self):
        self._groups: Dict[str, RedundancyGroup] = {}
        self._connections: Dict[str, List[str]] = {}  # group_id -> connection_ids
    
    def create_redundancy_group(self, name: str,
                                requirements: RedundancyRequirement) -> RedundancyGroup:
        """创建冗余组"""
        group = RedundancyGroup(
            id=str(uuid.uuid4()),
            name=name,
            type=requirements.level.value,
            devices=[],
            connections=[],
            requirements=requirements
        )
        
        self._groups[group.id] = group
        self._connections[group.id] = []
        
        return group
    
    def add_device_to_group(self, group_id: str, device_id: str) -> bool:
        """添加设备到冗余组"""
        if group_id not in self._groups:
            return False
        
        group = self._groups[group_id]
        if device_id not in group.devices:
            group.devices.append(device_id)
            return True
        
        return False
    
    def add_connection_to_group(self, group_id: str, connection_id: str) -> bool:
        """添加连接到冗余组"""
        if group_id not in self._groups:
            return False
        
        group = self._groups[group_id]
        if connection_id not in group.connections:
            group.connections.append(connection_id)
            self._connections[group_id].append(connection_id)
            return True
        
        return False
    
    def get_redundant_connections(self, device_id: str) -> List[str]:
        """获取设备的冗余连接"""
        redundant_connections = []
        
        for group in self._groups.values():
            if device_id in group.devices:
                redundant_connections.extend(group.connections)
        
        return redundant_connections
    
    def validate_redundancy(self, group_id: str) -> bool:
        """验证冗余要求"""
        if group_id not in self._groups:
            return False
        
        group = self._groups[group_id]
        requirements = group.requirements
        
        # 检查连接数
        connection_count = len(group.connections)
        if connection_count < requirements.min_connections:
            return False
        
        if requirements.max_connections and connection_count > requirements.max_connections:
            return False
        
        # 检查多样性
        for diversity_type in requirements.diversity:
            if not self._check_diversity(group, diversity_type):
                return False
        
        return True
    
    def _check_diversity(self, group: RedundancyGroup,
                        diversity_type: DiversityType) -> bool:
        """检查多样性"""
        if diversity_type == DiversityType.DEVICE:
            # 检查设备多样性
            devices = set(group.devices)
            return len(devices) >= 2
        
        elif diversity_type == DiversityType.RACK:
            # 检查机柜多样性
            racks = set()
            for device_id in group.devices:
                device = self._get_device(device_id)
                if device and device.rack:
                    racks.add(device.rack)
            return len(racks) >= 2
        
        elif diversity_type == DiversityType.PATH:
            # 检查路径多样性
            paths = set()
            for connection_id in group.connections:
                path = self._get_path(connection_id)
                if path:
                    paths.add(tuple(path))
            return len(paths) >= 2
        
        return True
    
    def _get_device(self, device_id: str) -> Optional[Device]:
        """获取设备（需要注入）"""
        # 实际实现需要从设备仓库获取
        pass
    
    def _get_path(self, connection_id: str) -> Optional[List[str]]:
        """获取路径（需要注入）"""
        # 实际实现需要从连接仓库获取
        pass

## 3. MLAG 特定模型

​```python
@dataclass
class MLAGDomain:
    """MLAG域"""
    id: str
    name: str
    device_a: Device
    device_b: Device
    peer_link: Connection
    keepalive: Connection
    member_connections: List[Connection]
    status: str = "ACTIVE"
    health: str = "HEALTHY"

class MLAGModel:
    """MLAG模型"""
    
    def create_domain(self, name: str,
                     device_a: Device,
                     device_b: Device,
                     peer_link: Connection,
                     keepalive: Connection) -> MLAGDomain:
        """创建MLAG域"""
        return MLAGDomain(
            id=str(uuid.uuid4()),
            name=name,
            device_a=device_a,
            device_b=device_b,
            peer_link=peer_link,
            keepalive=keepalive,
            member_connections=[]
        )
    
    def validate_mlag(self, domain: MLAGDomain) -> bool:
        """验证MLAG配置"""
        # 验证Peer-Link
        if not self._validate_peer_link(domain.peer_link):
            return False
        
        # 验证Keepalive
        if not self._validate_keepalive(domain.keepalive):
            return False
        
        # 验证成员连接
        for connection in domain.member_connections:
            if not self._validate_member_connection(connection, domain):
                return False
        
        return True
    
    def _validate_peer_link(self, peer_link: Connection) -> bool:
        """验证Peer-Link"""
        # Peer-Link必须使用高带宽端口
        if peer_link.source.speed < 40000:  # 40G+
            return False
        return True
    
    def _validate_keepalive(self, keepalive: Connection) -> bool:
        """验证Keepalive"""
        # Keepalive必须使用独立端口
        if keepalive.source.port_id == keepalive.destination.port_id:
            return False
        return True
    
    def _validate_member_connection(self, connection: Connection,
                                   domain: MLAGDomain) -> bool:
        """验证成员连接"""
        # 成员连接必须连接到MLAG域的设备
        valid_devices = {domain.device_a.id, domain.device_b.id}
        if connection.source.device_id not in valid_devices and \
           connection.destination.device_id not in valid_devices:
            return False
        return True
```