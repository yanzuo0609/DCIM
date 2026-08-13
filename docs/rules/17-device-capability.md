# Device Capability - 设备能力模型

## 1. 能力模型

设备能力包括：
- 端口数量和类型
- 支持的速率
- 支持的模块类型
- 冗余能力
- 协议支持
- 功能特性

## 2. 实现代码

```python
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)

class CapabilityType(str, Enum):
    SPEED = "speed"
    PORT_TYPE = "port_type"
    MODULE = "module"
    REDUNDANCY = "redundancy"
    PROTOCOL = "protocol"
    FEATURE = "feature"

@dataclass
class DeviceCapability:
    """设备能力"""
    device_id: str
    capabilities: Dict[str, Set[str]]
    
    def has_capability(self, capability_type: str, value: str) -> bool:
        """检查是否有特定能力"""
        if capability_type in self.capabilities:
            return value in self.capabilities[capability_type]
        return False
    
    def get_capabilities(self, capability_type: str) -> Set[str]:
        """获取特定类型的能力"""
        return self.capabilities.get(capability_type, set())
    
    def add_capability(self, capability_type: str, value: str) -> None:
        """添加能力"""
        if capability_type not in self.capabilities:
            self.capabilities[capability_type] = set()
        self.capabilities[capability_type].add(value)

class DeviceCapabilityManager:
    """设备能力管理器"""
    
    def __init__(self):
        self._capabilities: Dict[str, DeviceCapability] = {}
        self._capability_templates: Dict[str, Dict[str, Set[str]]] = {}
        
        self._load_default_templates()
    
    def _load_default_templates(self) -> None:
        """加载默认能力模板"""
        # 交换机模板
        self._capability_templates = {
            'core_switch': {
                'speeds': {'1000', '10000', '25000', '40000', '100000'},
                'port_types': {'ETHERNET'},
                'modules': {'SFP', 'SFP+', 'SFP28', 'QSFP+', 'QSFP28'},
                'redundancy': {'active_active', 'active_standby', 'mlag'},
                'protocols': {'ETHERNET', 'FIBRE_CHANNEL'},
                'features': {'vlan', 'stp', 'ospf', 'bgp', 'mpls'}
            },
            'aggregation_switch': {
                'speeds': {'1000', '10000', '25000', '40000'},
                'port_types': {'ETHERNET'},
                'modules': {'SFP', 'SFP+', 'SFP28', 'QSFP+'},
                'redundancy': {'active_active', 'mlag'},
                'protocols': {'ETHERNET'},
                'features': {'vlan', 'stp', 'ospf', 'bgp'}
            },
            'access_switch': {
                'speeds': {'100', '1000', '10000'},
                'port_types': {'ETHERNET'},
                'modules': {'SFP', 'SFP+'},
                'redundancy': {'active_active'},
                'protocols': {'ETHERNET'},
                'features': {'vlan', 'stp', 'poe'}
            },
            'spine_switch': {
                'speeds': {'10000', '25000', '40000', '100000'},
                'port_types': {'ETHERNET'},
                'modules': {'QSFP+', 'QSFP28', 'QSFP-DD'},
                'redundancy': {'active_active'},
                'protocols': {'ETHERNET'},
                'features': {'vlan', 'ospf', 'bgp', 'ecmp'}
            },
            'leaf_switch': {
                'speeds': {'1000', '10000', '25000'},
                'port_types': {'ETHERNET'},
                'modules': {'SFP+', 'SFP28', 'QSFP+'},
                'redundancy': {'active_active', 'mlag'},
                'protocols': {'ETHERNET'},
                'features': {'vlan', 'stp', 'ospf', 'bgp'}
            },
            'server': {
                'speeds': {'1000', '10000', '25000'},
                'port_types': {'ETHERNET', 'FIBRE_CHANNEL'},
                'modules': {'SFP', 'SFP+', 'SFP28'},
                'redundancy': {'active_active'},
                'protocols': {'ETHERNET', 'FIBRE_CHANNEL'},
                'features': {'pcie', 'rdma', 'roce', 'nvme'}
            },
            'firewall': {
                'speeds': {'1000', '10000'},
                'port_types': {'ETHERNET'},
                'modules': {'SFP', 'SFP+'},
                'redundancy': {'active_standby'},
                'protocols': {'ETHERNET'},
                'features': {'nat', 'vpn', 'ids', 'ips', 'app_control'}
            },
            'load_balancer': {
                'speeds': {'1000', '10000'},
                'port_types': {'ETHERNET'},
                'modules': {'SFP', 'SFP+'},
                'redundancy': {'active_active'},
                'protocols': {'ETHERNET'},
                'features': {'ssl_offload', 'persistence', 'health_check'}
            }
        }
    
    def get_capability(self, device_id: str) -> Optional[DeviceCapability]:
        """获取设备能力"""
        return self._capabilities.get(device_id)
    
    def get_capability_by_role(self, role: DeviceRole) -> Dict[str, Set[str]]:
        """根据角色获取能力模板"""
        role_map = {
            DeviceRole.CORE_SWITCH: 'core_switch',
            DeviceRole.AGGREGATION_SWITCH: 'aggregation_switch',
            DeviceRole.ACCESS_SWITCH: 'access_switch',
            DeviceRole.SPINE_SWITCH: 'spine_switch',
            DeviceRole.LEAF_SWITCH: 'leaf_switch',
            DeviceRole.SERVER: 'server',
            DeviceRole.FIREWALL: 'firewall',
            DeviceRole.LOAD_BALANCER: 'load_balancer',
        }
        
        template_name = role_map.get(role)
        if template_name:
            return self._capability_templates.get(template_name, {})
        
        return {}
    
    def add_device_capability(self, device_id: str, 
                             capabilities: Dict[str, Set[str]]) -> None:
        """添加设备能力"""
        self._capabilities[device_id] = DeviceCapability(device_id, capabilities)
    
    def initialize_device(self, device: Device) -> None:
        """初始化设备能力"""
        capabilities = self.get_capability_by_role(device.role)
        
        # 转换为集合
        capability_sets = {}
        for key, value in capabilities.items():
            capability_sets[key] = set(value)
        
        self.add_device_capability(device.id, capability_sets)
    
    def check_compatibility(self, device1: Device, device2: Device) -> bool:
        """检查设备兼容性"""
        cap1 = self.get_capability(device1.id)
        cap2 = self.get_capability(device2.id)
        
        if not cap1 or not cap2:
            return False
        
        # 检查速率兼容性
        speeds1 = cap1.get_capabilities('speeds')
        speeds2 = cap2.get_capabilities('speeds')
        if not speeds1.intersection(speeds2):
            return False
        
        # 检查协议兼容性
        protocols1 = cap1.get_capabilities('protocols')
        protocols2 = cap2.get_capabilities('protocols')
        if not protocols1.intersection(protocols2):
            return False
        
        return True
    
    def get_supported_speeds(self, device_id: str) -> Set[str]:
        """获取设备支持的速率"""
        cap = self.get_capability(device_id)
        if cap:
            return cap.get_capabilities('speeds')
        return set()
    
    def get_supported_modules(self, device_id: str) -> Set[str]:
        """获取设备支持的模块"""
        cap = self.get_capability(device_id)
        if cap:
            return cap.get_capabilities('modules')
        return set()

class CapabilityValidator:
    """能力验证器"""
    
    def __init__(self, capability_manager: DeviceCapabilityManager):
        self.capability_manager = capability_manager
    
    def validate_port_capability(self, device: Device, port: Port) -> bool:
        """验证端口能力"""
        capabilities = self.capability_manager.get_capability(device.id)
        if not capabilities:
            return False
        
        # 检查端口速率是否在设备支持范围内
        speeds = capabilities.get_capabilities('speeds')
        if str(port.speed) not in speeds:
            return False
        
        return True
    
    def validate_connection_capability(self, source: Device, target: Device,
                                      connection: Connection) -> bool:
        """验证连接能力"""
        # 检查设备兼容性
        if not self.capability_manager.check_compatibility(source, target):
            return False
        
        # 检查连接速率
        source_cap = self.capability_manager.get_capability(source.id)
        target_cap = self.capability_manager.get_capability(target.id)
        
        if not source_cap or not target_cap:
            return False
        
        source_speeds = source_cap.get_capabilities('speeds')
        target_speeds = target_cap.get_capabilities('speeds')
        common_speeds = source_speeds.intersection(target_speeds)
        
        # 检查连接速率是否在共同支持的范围内
        # 实际实现需要获取连接速率
        return True
```