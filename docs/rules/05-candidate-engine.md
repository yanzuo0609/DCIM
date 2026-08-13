# Candidate Engine - 候选连接生成引擎

## 1. 功能概述

候选引擎负责生成所有可能的连接候选，为后续的约束检查和评分优化提供基础。

## 2. 核心算法

### 2.1 候选生成策略

策略1: 全连接（All-to-All）

- 源设备的所有可用端口 → 目标设备的所有可用端口
- 复杂度: O(N × M)

策略2: 按角色匹配

- 根据端口角色匹配（UPLINK → DOWNLINK）
- 复杂度: O(N × M) 但更少候选

策略3: 按速率匹配

- 相同速率的端口配对
- 复杂度: O(N × M) 但更少候选

策略4: 智能过滤

- 结合多种过滤条件
- 复杂度: O(N × M) 但最优

text

```
## 3. 实现代码

​```python
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import itertools
import logging

logger = logging.getLogger(__name__)

class CandidateGenerationStrategy(str, Enum):
    ALL_TO_ALL = "all_to_all"
    ROLE_MATCH = "role_match"
    SPEED_MATCH = "speed_match"
    INTELLIGENT = "intelligent"

@dataclass
class Candidate:
    """连接候选"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    source_device_id: str
    source_port_id: str
    target_device_id: str
    target_port_id: str
    
    # 匹配信息
    match_type: str
    match_score: int = 0
    
    # 参数
    parameters: Dict[str, Any] = field(default_factory=dict)
    
    # 状态
    status: str = "PENDING"  # PENDING, VALIDATED, REJECTED, SCORED
    
    # 元数据
    created_at: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

class CandidateEngine:
    """候选连接生成引擎"""
    
    def __init__(self, 
                 strategy: CandidateGenerationStrategy = CandidateGenerationStrategy.INTELLIGENT,
                 max_candidates: int = 10000,
                 batch_size: int = 1000):
        self.strategy = strategy
        self.max_candidates = max_candidates
        self.batch_size = batch_size
        self._generated_count = 0
    
    async def generate_candidates(self, 
                                  source_devices: List[Device],
                                  target_devices: List[Device],
                                  constraints: Optional[Dict[str, Any]] = None) -> List[Candidate]:
        """生成候选连接"""
        self._generated_count = 0
        candidates = []
        
        for source_device in source_devices:
            for target_device in target_devices:
                # 获取可用端口
                source_ports = [p for p in source_device.ports if p.status == PortStatus.AVAILABLE]
                target_ports = [p for p in target_device.ports if p.status == PortStatus.AVAILABLE]
                
                if not source_ports or not target_ports:
                    continue
                
                # 根据策略生成候选
                device_candidates = await self._generate_device_candidates(
                    source_device, target_device, source_ports, target_ports, constraints
                )
                
                candidates.extend(device_candidates)
                
                if len(candidates) >= self.max_candidates:
                    logger.warning(f"Reached max candidates limit: {self.max_candidates}")
                    break
        
        logger.info(f"Generated {len(candidates)} candidates")
        return candidates
    
    async def _generate_device_candidates(self,
                                         source_device: Device,
                                         target_device: Device,
                                         source_ports: List[Port],
                                         target_ports: List[Port],
                                         constraints: Optional[Dict[str, Any]]) -> List[Candidate]:
        """为设备对生成候选"""
        candidates = []
        
        if self.strategy == CandidateGenerationStrategy.ALL_TO_ALL:
            candidates = self._all_to_all(source_device, target_device, source_ports, target_ports)
        
        elif self.strategy == CandidateGenerationStrategy.ROLE_MATCH:
            candidates = self._role_match(source_device, target_device, source_ports, target_ports)
        
        elif self.strategy == CandidateGenerationStrategy.SPEED_MATCH:
            candidates = self._speed_match(source_device, target_device, source_ports, target_ports)
        
        else:  # INTELLIGENT
            candidates = self._intelligent(source_device, target_device, source_ports, target_ports)
        
        # 应用约束过滤
        if constraints:
            candidates = self._apply_constraints(candidates, constraints)
        
        return candidates
    
    def _all_to_all(self, source_device: Device, target_device: Device,
                    source_ports: List[Port], target_ports: List[Port]) -> List[Candidate]:
        """全连接策略"""
        candidates = []
        for source_port in source_ports:
            for target_port in target_ports:
                candidates.append(Candidate(
                    source_device_id=source_device.id,
                    source_port_id=source_port.id,
                    target_device_id=target_device.id,
                    target_port_id=target_port.id,
                    match_type="all_to_all"
                ))
        return candidates
    
    def _role_match(self, source_device: Device, target_device: Device,
                    source_ports: List[Port], target_ports: List[Port]) -> List[Candidate]:
        """角色匹配策略"""
        candidates = []
        
        for source_port in source_ports:
            for target_port in target_ports:
                # 检查角色匹配
                if self._is_role_compatible(source_port.role, target_port.role):
                    candidates.append(Candidate(
                        source_device_id=source_device.id,
                        source_port_id=source_port.id,
                        target_device_id=target_device.id,
                        target_port_id=target_port.id,
                        match_type="role_match",
                        match_score=10
                    ))
        return candidates
    
    def _speed_match(self, source_device: Device, target_device: Device,
                     source_ports: List[Port], target_ports: List[Port]) -> List[Candidate]:
        """速率匹配策略"""
        candidates = []
        
        for source_port in source_ports:
            for target_port in target_ports:
                # 检查速率匹配
                if source_port.speed == target_port.speed:
                    candidates.append(Candidate(
                        source_device_id=source_device.id,
                        source_port_id=source_port.id,
                        target_device_id=target_device.id,
                        target_port_id=target_port.id,
                        match_type="speed_match",
                        match_score=15
                    ))
                elif source_port.speed in target_port.supported_speeds:
                    candidates.append(Candidate(
                        source_device_id=source_device.id,
                        source_port_id=source_port.id,
                        target_device_id=target_device.id,
                        target_port_id=target_port.id,
                        match_type="speed_match",
                        match_score=5
                    ))
        return candidates
    
    def _intelligent(self, source_device: Device, target_device: Device,
                     source_ports: List[Port], target_ports: List[Port]) -> List[Candidate]:
        """智能匹配策略"""
        candidates = []
        
        # 按速率分组
        source_by_speed = {}
        for port in source_ports:
            if port.speed not in source_by_speed:
                source_by_speed[port.speed] = []
            source_by_speed[port.speed].append(port)
        
        target_by_speed = {}
        for port in target_ports:
            if port.speed not in target_by_speed:
                target_by_speed[port.speed] = []
            target_by_speed[port.speed].append(port)
        
        # 优先匹配相同速率
        common_speeds = set(source_by_speed.keys()) & set(target_by_speed.keys())
        for speed in common_speeds:
            for src_port in source_by_speed[speed]:
                for tgt_port in target_by_speed[speed]:
                    score = self._calculate_compatibility(src_port, tgt_port)
                    candidates.append(Candidate(
                        source_device_id=source_device.id,
                        source_port_id=src_port.id,
                        target_device_id=target_device.id,
                        target_port_id=tgt_port.id,
                        match_type="intelligent",
                        match_score=score,
                        parameters={
                            'speed': speed,
                            'compatibility_score': score
                        }
                    ))
        
        return candidates
    
    def _is_role_compatible(self, role1: PortRole, role2: PortRole) -> bool:
        """检查端口角色是否兼容"""
        compatible_pairs = {
            (PortRole.UPLINK, PortRole.DOWNLINK),
            (PortRole.DOWNLINK, PortRole.UPLINK),
            (PortRole.PEER_LINK, PortRole.PEER_LINK),
            (PortRole.SERVER, PortRole.DOWNLINK),
            (PortRole.DOWNLINK, PortRole.SERVER),
        }
        return (role1, role2) in compatible_pairs
    
    def _calculate_compatibility(self, port1: Port, port2: Port) -> int:
        """计算端口兼容性分数"""
        score = 0
        
        # 速率匹配
        if port1.speed == port2.speed:
            score += 20
        elif port1.speed in port2.supported_speeds:
            score += 10
        
        # 介质匹配
        if port1.media == port2.media:
            score += 10
        
        # 连接器匹配
        if port1.connector == port2.connector:
            score += 10
        
        return score
    
    def _apply_constraints(self, candidates: List[Candidate], 
                          constraints: Dict[str, Any]) -> List[Candidate]:
        """应用约束过滤候选"""
        filtered = []
        
        for candidate in candidates:
            if self._passes_constraints(candidate, constraints):
                filtered.append(candidate)
        
        return filtered
    
    def _passes_constraints(self, candidate: Candidate, constraints: Dict[str, Any]) -> bool:
        """检查候选是否通过约束"""
        # 速度约束
        if 'min_speed' in constraints:
            speed = candidate.parameters.get('speed', 0)
            if speed < constraints['min_speed']:
                return False
        
        # 介质约束
        if 'media' in constraints:
            media = candidate.parameters.get('media')
            if media not in constraints['media']:
                return False
        
        return True
    
    def _apply_constraints(self, candidates: List[Candidate], 
                          constraints: Dict[str, Any]) -> List[Candidate]:
        """应用约束过滤候选"""
        filtered = []
        
        for candidate in candidates:
            if self._passes_constraints(candidate, constraints):
                filtered.append(candidate)
        
        return filtered
    
    def _passes_constraints(self, candidate: Candidate, constraints: Dict[str, Any]) -> bool:
        """检查候选是否通过约束"""
        # 速度约束
        if 'min_speed' in constraints:
            speed = candidate.parameters.get('speed', 0)
            if speed < constraints['min_speed']:
                return False
        
        # 介质约束
        if 'media' in constraints:
            media = candidate.parameters.get('media')
            if media not in constraints['media']:
                return False
        
        return True

    def sort_by_score(self, candidates: List[Candidate]) -> List[Candidate]:
        """按分数排序候选"""
        return sorted(candidates, key=lambda c: c.match_score, reverse=True)
    
    def deduplicate(self, candidates: List[Candidate]) -> List[Candidate]:
        """去重候选"""
        seen = set()
        unique = []
        
        for candidate in candidates:
            key = (candidate.source_device_id, candidate.source_port_id,
                   candidate.target_device_id, candidate.target_port_id)
            if key not in seen:
                seen.add(key)
                unique.append(candidate)
        
        return unique
```



## 4. 候选优化策略

python

```
class CandidateOptimizer:
    """候选优化器"""
    
    def __init__(self):
        self.filters = []
    
    def add_filter(self, filter_func: Callable) -> None:
        """添加过滤器"""
        self.filters.append(filter_func)
    
    async def optimize(self, candidates: List[Candidate]) -> List[Candidate]:
        """优化候选列表"""
        result = candidates
        
        # 应用过滤器
        for filter_func in self.filters:
            result = await filter_func(result)
        
        # 限制数量
        if len(result) > 10000:
            result = result[:10000]
        
        return result
    
    def create_filter_by_port_availability(self) -> Callable:
        """创建端口可用性过滤器"""
        async def filter_func(candidates: List[Candidate]) -> List[Candidate]:
            return [c for c in candidates if c.status == "PENDING"]
        return filter_func
    
    def create_filter_by_speed(self, min_speed: int) -> Callable:
        """创建速率过滤器"""
        async def filter_func(candidates: List[Candidate]) -> List[Candidate]:
            filtered = []
            for c in candidates:
                speed = c.parameters.get('speed', 0)
                if speed >= min_speed:
                    filtered.append(c)
            return filtered
        return filter_func
    
    def create_limit_filter(self, limit: int) -> Callable:
        """创建数量限制过滤器"""
        async def filter_func(candidates: List[Candidate]) -> List[Candidate]:
            return candidates[:limit] if len(candidates) > limit else candidates
        return filter_func
```