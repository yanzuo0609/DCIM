# Resource Allocation - 资源分配引擎

## 1. 资源类型

| 资源类型 | 说明 | 状态 |
|---------|------|------|
| Port | 物理端口 | AVAILABLE, RESERVED, ALLOCATED, LOCKED |
| Module | 光模块/收发器 | AVAILABLE, RESERVED, ALLOCATED |
| Cable | 线缆 | AVAILABLE, RESERVED, ALLOCATED |
| Patch Panel | 配线架端口 | AVAILABLE, ALLOCATED |
| ODF | 光配架端口 | AVAILABLE, ALLOCATED |
| Rack Position | 机柜位置 | AVAILABLE, OCCUPIED |

## 2. 分配器实现

```python
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)

class ResourceStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RESERVED = "RESERVED"
    ALLOCATED = "ALLOCATED"
    LOCKED = "LOCKED"
    FAILED = "FAILED"

@dataclass
class ResourceAllocation:
    """资源分配"""
    resource_id: str
    resource_type: str
    connection_id: str
    status: ResourceStatus = ResourceStatus.ALLOCATED
    allocated_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class AllocationResult:
    """分配结果"""
    successful: bool
    allocations: List[ResourceAllocation]
    errors: List[str]
    warnings: List[str]

class ResourceAllocator:
    """资源分配器"""
    
    def __init__(self):
        self._resources: Dict[str, Dict[str, Any]] = {}
        self._allocations: List[ResourceAllocation] = []
        self._lock = asyncio.Lock()
    
    async def allocate_for_connection(self, connection: Connection,
                                     context: Dict[str, Any]) -> AllocationResult:
        """为连接分配资源"""
        async with self._lock:
            allocations = []
            errors = []
            warnings = []
            
            # 分配端口
            port_allocations = await self._allocate_ports(connection, context)
            allocations.extend(port_allocations)
            
            # 分配模块
            module_allocations = await self._allocate_modules(connection, context)
            allocations.extend(module_allocations)
            
            # 分配线缆
            cable_allocations = await self._allocate_cable(connection, context)
            allocations.extend(cable_allocations)
            
            # 分配配线架端口
            patch_allocations = await self._allocate_patch_panel(connection, context)
            allocations.extend(patch_allocations)
            
            # 检查分配结果
            for allocation in allocations:
                if allocation.status == ResourceStatus.FAILED:
                    errors.append(f"Failed to allocate {allocation.resource_type}: {allocation.resource_id}")
            
            if errors:
                # 回滚已分配的资源
                await self._rollback(allocations)
            
            return AllocationResult(
                successful=len(errors) == 0,
                allocations=allocations,
                errors=errors,
                warnings=warnings
            )
    
    async def _allocate_ports(self, connection: Connection,
                             context: Dict[str, Any]) -> List[ResourceAllocation]:
        """分配端口"""
        allocations = []
        
        # 分配源端口
        source_port = context.get('source_port')
        if source_port:
            allocation = await self._allocate_resource(
                resource_id=source_port.id,
                resource_type='port',
                connection_id=connection.id,
                context=context
            )
            allocations.append(allocation)
            
            # 更新端口状态
            source_port.status = PortStatus.ALLOCATED
            source_port.allocated_to = connection.id
        
        # 分配目标端口
        target_port = context.get('target_port')
        if target_port:
            allocation = await self._allocate_resource(
                resource_id=target_port.id,
                resource_type='port',
                connection_id=connection.id,
                context=context
            )
            allocations.append(allocation)
            
            target_port.status = PortStatus.ALLOCATED
            target_port.allocated_to = connection.id
        
        return allocations
    
    async def _allocate_modules(self, connection: Connection,
                               context: Dict[str, Any]) -> List[ResourceAllocation]:
        """分配模块"""
        allocations = []
        
        # 分配源模块
        source_module = context.get('source_module')
        if source_module:
            allocation = await self._allocate_resource(
                resource_id=source_module.id,
                resource_type='module',
                connection_id=connection.id,
                context=context
            )
            allocations.append(allocation)
            
            source_module.status = ModuleStatus.ALLOCATED
            source_module.allocated_to = connection.id
        
        # 分配目标模块
        target_module = context.get('target_module')
        if target_module:
            allocation = await self._allocate_resource(
                resource_id=target_module.id,
                resource_type='module',
                connection_id=connection.id,
                context=context
            )
            allocations.append(allocation)
            
            target_module.status = ModuleStatus.ALLOCATED
            target_module.allocated_to = connection.id
        
        return allocations
    
    async def _allocate_cable(self, connection: Connection,
                             context: Dict[str, Any]) -> List[ResourceAllocation]:
        """分配线缆"""
        cable = context.get('cable')
        if not cable:
            return []
        
        allocation = await self._allocate_resource(
            resource_id=cable.id,
            resource_type='cable',
            connection_id=connection.id,
            context=context
        )
        
        if allocation.status == ResourceStatus.ALLOCATED:
            cable.status = CableStatus.ALLOCATED
            cable.allocated_to = connection.id
        
        return [allocation]
    
    async def _allocate_patch_panel(self, connection: Connection,
                                   context: Dict[str, Any]) -> List[ResourceAllocation]:
        """分配配线架端口"""
        allocations = []
        
        patch_panels = context.get('patch_panels', [])
        for panel in patch_panels:
            for port in panel.ports:
                if port.status == PortStatus.AVAILABLE:
                    allocation = await self._allocate_resource(
                        resource_id=port.id,
                        resource_type='patch_panel_port',
                        connection_id=connection.id,
                        context=context
                    )
                    allocations.append(allocation)
                    port.status = PortStatus.ALLOCATED
                    port.connected_to = connection.id
                    break  # 每个面板分配一个端口
        
        return allocations
    
    async def _allocate_resource(self, resource_id: str,
                                resource_type: str,
                                connection_id: str,
                                context: Dict[str, Any]) -> ResourceAllocation:
        """分配单个资源"""
        # 检查资源是否可用
        if not await self._is_resource_available(resource_id, resource_type):
            return ResourceAllocation(
                resource_id=resource_id,
                resource_type=resource_type,
                connection_id=connection_id,
                status=ResourceStatus.FAILED,
                metadata={'reason': 'Resource not available'}
            )
        
        allocation = ResourceAllocation(
            resource_id=resource_id,
            resource_type=resource_type,
            connection_id=connection_id
        )
        
        self._allocations.append(allocation)
        self._resources.setdefault(resource_type, {})[resource_id] = allocation
        
        return allocation
    
    async def _is_resource_available(self, resource_id: str,
                                    resource_type: str) -> bool:
        """检查资源是否可用"""
        # 检查是否已被分配
        for allocation in self._allocations:
            if allocation.resource_id == resource_id and \
               allocation.resource_type == resource_type:
                if allocation.status == ResourceStatus.ALLOCATED:
                    return False
        
        return True
    
    async def _rollback(self, allocations: List[ResourceAllocation]) -> None:
        """回滚分配"""
        for allocation in allocations:
            if allocation.status == ResourceStatus.ALLOCATED:
                allocation.status = ResourceStatus.AVAILABLE
        
        logger.warning(f"Rolled back {len(allocations)} allocations")
    
    async def release(self, connection_id: str) -> None:
        """释放连接占用的资源"""
        to_release = [a for a in self._allocations if a.connection_id == connection_id]
        
        for allocation in to_release:
            allocation.status = ResourceStatus.AVAILABLE
        
        self._allocations = [a for a in self._allocations if a.connection_id != connection_id]
        
        logger.info(f"Released {len(to_release)} resources for connection {connection_id}")
    
    def get_allocations(self, connection_id: str) -> List[ResourceAllocation]:
        """获取连接的资源分配"""
        return [a for a in self._allocations if a.connection_id == connection_id]
    
    def get_utilization(self) -> Dict[str, float]:
        """获取资源利用率"""
        utilization = {}
        
        for resource_type, resources in self._resources.items():
            total = len(resources)
            allocated = len([r for r in resources.values() if r.status == ResourceStatus.ALLOCATED])
            utilization[resource_type] = allocated / total if total > 0 else 0
        
        return utilization
```