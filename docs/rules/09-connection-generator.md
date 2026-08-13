# Connection Generator - 连接生成器

## 1. 功能概述

连接生成器负责将优化后的候选转换为最终的连接对象，包括物理连接和逻辑链路。

## 2. 生成流程

优化结果 → 候选确认 → 资源分配 → 连接创建 → 路径构建 → 连接返回

text

```
## 3. 实现代码

​```python
from typing import List, Dict, Any, Optional, Set
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

class ConnectionGenerator:
    """连接生成器"""
    
    def __init__(self, repository: Optional[IConnectionRepository] = None):
        self.repository = repository
    
    async def generate_connections(self, 
                                  selected_candidates: List[Candidate],
                                  context: Dict[str, Any]) -> List[Connection]:
        """生成连接"""
        connections = []
        
        for candidate in selected_candidates:
            connection = await self._create_connection(candidate, context)
            connections.append(connection)
        
        logger.info(f"Generated {len(connections)} connections")
        return connections
    
    async def _create_connection(self, candidate: Candidate,
                                 context: Dict[str, Any]) -> Connection:
        """创建单个连接"""
        # 获取设备信息
        source_device = context.get('source_device')
        target_device = context.get('target_device')
        source_port = context.get('source_port')
        target_port = context.get('target_port')
        
        # 获取模块信息
        source_module = context.get('source_module')
        target_module = context.get('target_module')
        
        # 获取线缆信息
        cable = context.get('cable')
        
        # 创建连接端点
        source_end = ConnectionEnd(
            device_id=source_device.id if source_device else '',
            device_name=source_device.name if source_device else '',
            port_id=source_port.id if source_port else '',
            port_name=source_port.name if source_port else '',
            module_id=source_module.id if source_module else None,
            module_part_number=source_module.part_number if source_module else None
        )
        
        target_end = ConnectionEnd(
            device_id=target_device.id if target_device else '',
            device_name=target_device.name if target_device else '',
            port_id=target_port.id if target_port else '',
            port_name=target_port.name if target_port else '',
            module_id=target_module.id if target_module else None,
            module_part_number=target_module.part_number if target_module else None
        )
        
        # 创建路径
        path = await self._create_path(candidate, context)
        
        # 创建连接
        connection = Connection(
            id=str(uuid.uuid4()),
            name=f"{source_device.name}_{source_port.name}_to_{target_device.name}_{target_port.name}",
            source=source_end,
            destination=target_end,
            cable_id=cable.id if cable else None,
            cable=cable,
            type=ConnectionType.PHYSICAL,
            link_type=self._determine_link_type(source_device, target_device),
            path=path,
            status=ConnectionStatus.PROPOSED,
            metadata={
                'candidate_id': candidate.id,
                'generated_at': datetime.now().isoformat()
            }
        )
        
        return connection
    
    async def _create_path(self, candidate: Candidate,
                          context: Dict[str, Any]) -> Optional[ConnectionPath]:
        """创建物理路径"""
        path_nodes = []
        total_length = 0
        
        # 源设备到配线架
        patch_panels = context.get('patch_panels', [])
        odfs = context.get('odfs', [])
        
        if patch_panels:
            path_nodes.append({
                'type': 'patch_panel',
                'id': patch_panels[0].id,
                'name': patch_panels[0].name
            })
            total_length += 2  # 跳线长度
        
        if odfs:
            path_nodes.append({
                'type': 'odf',
                'id': odfs[0].id,
                'name': odfs[0].name
            })
            total_length += 5  # 光纤长度
        
        return ConnectionPath(
            nodes=path_nodes,
            total_length_m=total_length,
            hops=len(path_nodes)
        )
    
    def _determine_link_type(self, source_device: Device,
                            target_device: Device) -> LinkType:
        """确定链路类型"""
        source_role = source_device.role
        target_role = target_device.role
        
        # 拓扑链路类型
        if source_role == DeviceRole.CORE_SWITCH and target_role == DeviceRole.AGGREGATION_SWITCH:
            return LinkType.UPLINK
        elif source_role == DeviceRole.AGGREGATION_SWITCH and target_role == DeviceRole.ACCESS_SWITCH:
            return LinkType.DOWNLINK
        elif source_role == DeviceRole.ACCESS_SWITCH and target_role == DeviceRole.SERVER:
            return LinkType.ACCESS
        
        return LinkType.UPLINK

class LogicalLinkGenerator:
    """逻辑链路生成器"""
    
    async def generate(self, connections: List[Connection],
                      context: Dict[str, Any]) -> List[Connection]:
        """生成逻辑链路"""
        logical_links = []
        
        for connection in connections:
            logical_link = await self._create_logical_link(connection, context)
            logical_links.append(logical_link)
        
        return logical_links
    
    async def _create_logical_link(self, physical: Connection,
                                   context: Dict[str, Any]) -> Connection:
        """创建逻辑链路"""
        return Connection(
            id=str(uuid.uuid4()),
            name=f"Logical_{physical.name}",
            source=physical.source,
            destination=physical.destination,
            type=ConnectionType.LOGICAL,
            link_type=physical.link_type,
            metadata={
                'physical_connection_id': physical.id,
                'logical': True
            }
        )
```