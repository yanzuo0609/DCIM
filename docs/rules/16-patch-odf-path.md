# Patch Panel / ODF Path - 配线架和光配架路径管理

## 1. 路径模型

Server → Patch Panel → ODF → Fiber → ODF → Patch Panel → Switch

text

```
## 2. 实现代码

​```python
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)

class PathNodeType(str, Enum):
    DEVICE = "device"
    PATCH_PANEL = "patch_panel"
    ODF = "odf"
    SPLICE = "splice"
    CONNECTOR = "connector"

@dataclass
class PathNode:
    """路径节点"""
    id: str
    type: PathNodeType
    name: str
    device_id: Optional[str] = None
    port_id: Optional[str] = None
    position: Optional[int] = None

@dataclass
class PhysicalPath:
    """物理路径"""
    id: str
    source_device_id: str
    source_port_id: str
    target_device_id: str
    target_port_id: str
    nodes: List[PathNode]
    total_length: float
    cable_ids: List[str]
    is_complete: bool = False

class PatchPanelManager:
    """配线架管理器"""
    
    def __init__(self):
        self._patch_panels: Dict[str, PatchPanel] = {}
        self._odfs: Dict[str, ODF] = {}
    
    def add_patch_panel(self, panel: PatchPanel) -> None:
        """添加配线架"""
        self._patch_panels[panel.id] = panel
    
    def add_odf(self, odf: ODF) -> None:
        """添加ODF"""
        self._odfs[odf.id] = odf
    
    def get_patch_panel(self, panel_id: str) -> Optional[PatchPanel]:
        """获取配线架"""
        return self._patch_panels.get(panel_id)
    
    def get_odf(self, odf_id: str) -> Optional[ODF]:
        """获取ODF"""
        return self._odfs.get(odf_id)
    
    def find_available_port(self, panel_id: str) -> Optional[PatchPanelPort]:
        """查找可用端口"""
        panel = self._patch_panels.get(panel_id)
        if not panel:
            return None
        
        for port in panel.ports:
            if port.status == PortStatus.AVAILABLE:
                return port
        
        return None

class PathBuilder:
    """路径构建器"""
    
    def __init__(self, panel_manager: PatchPanelManager):
        self.panel_manager = panel_manager
        self._path_cache: Dict[str, PhysicalPath] = {}
    
    async def build_path(self, source_device_id: str,
                        source_port_id: str,
                        target_device_id: str,
                        target_port_id: str) -> PhysicalPath:
        """构建物理路径"""
        # 检查缓存
        cache_key = f"{source_device_id}:{source_port_id}:{target_device_id}:{target_port_id}"
        if cache_key in self._path_cache:
            return self._path_cache[cache_key]
        
        nodes = []
        cable_ids = []
        total_length = 0
        
        # 源设备
        nodes.append(PathNode(
            id=str(uuid.uuid4()),
            type=PathNodeType.DEVICE,
            name=f"Device: {source_device_id}",
            device_id=source_device_id,
            port_id=source_port_id
        ))
        
        # 查找配线架路径
        panel_paths = await self._find_panel_path(source_device_id, target_device_id)
        
        for panel in panel_paths:
            nodes.append(PathNode(
                id=str(uuid.uuid4()),
                type=PathNodeType.PATCH_PANEL,
                name=f"Patch Panel: {panel.id}",
                device_id=panel.id
            ))
            total_length += 2  # 跳线长度
            
            # 分配端口
            port = self.panel_manager.find_available_port(panel.id)
            if port:
                port.status = PortStatus.ALLOCATED
        
        # 查找ODF路径
        odf_paths = await self._find_odf_path(source_device_id, target_device_id)
        
        for odf in odf_paths:
            nodes.append(PathNode(
                id=str(uuid.uuid4()),
                type=PathNodeType.ODF,
                name=f"ODF: {odf.id}",
                device_id=odf.id
            ))
            total_length += 5  # 光纤长度
        
        # 目标设备
        nodes.append(PathNode(
            id=str(uuid.uuid4()),
            type=PathNodeType.DEVICE,
            name=f"Device: {target_device_id}",
            device_id=target_device_id,
            port_id=target_port_id
        ))
        
        path = PhysicalPath(
            id=str(uuid.uuid4()),
            source_device_id=source_device_id,
            source_port_id=source_port_id,
            target_device_id=target_device_id,
            target_port_id=target_port_id,
            nodes=nodes,
            total_length=total_length,
            cable_ids=cable_ids,
            is_complete=True
        )
        
        # 缓存路径
        self._path_cache[cache_key] = path
        
        return path
    
    async def _find_panel_path(self, source_device_id: str,
                              target_device_id: str) -> List[PatchPanel]:
        """查找配线架路径"""
        # 简化实现：返回所有配线架
        return list(self.panel_manager._patch_panels.values())
    
    async def _find_odf_path(self, source_device_id: str,
                            target_device_id: str) -> List[ODF]:
        """查找ODF路径"""
        # 简化实现：返回所有ODF
        return list(self.panel_manager._odfs.values())
    
    def get_path(self, path_id: str) -> Optional[PhysicalPath]:
        """获取路径"""
        for path in self._path_cache.values():
            if path.id == path_id:
                return path
        return None
    
    def get_paths_for_device(self, device_id: str) -> List[PhysicalPath]:
        """获取设备的所有路径"""
        return [p for p in self._path_cache.values() 
                if p.source_device_id == device_id or p.target_device_id == device_id]

class PathValidator:
    """路径验证器"""
    
    def __init__(self):
        self._validators = []
    
    def add_validator(self, validator: Callable) -> None:
        """添加验证器"""
        self._validators.append(validator)
    
    async def validate_path(self, path: PhysicalPath) -> bool:
        """验证路径"""
        for validator in self._validators:
            if not await validator(path):
                return False
        return True
    
    def create_panel_availability_validator(self) -> Callable:
        """创建配线架可用性验证器"""
        async def validator(path: PhysicalPath) -> bool:
            for node in path.nodes:
                if node.type == PathNodeType.PATCH_PANEL:
                    panel = self.panel_manager.get_patch_panel(node.device_id)
                    if panel:
                        # 检查是否有可用端口
                        has_available = any(p.status == PortStatus.AVAILABLE 
                                          for p in panel.ports)
                        if not has_available:
                            return False
            return True
        return validator
    
    def create_path_length_validator(self, max_length: float) -> Callable:
        """创建路径长度验证器"""
        async def validator(path: PhysicalPath) -> bool:
            return path.total_length <= max_length
        return validator
```