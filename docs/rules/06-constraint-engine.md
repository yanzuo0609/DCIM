# Constraint Engine - 约束检查引擎

## 1. 约束类型

### 1.1 Hard Constraints（硬约束）
- 不满足则直接拒绝候选
- 优先级最高

### 1.2 Soft Constraints（软约束）
- 不满足只降低评分
- 不会导致候选被拒绝

## 2. 约束检查器

```python
from typing import List, Dict, Any, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ConstraintLevel(str, Enum):
    HARD = "hard"
    SOFT = "soft"

class ConstraintType(str, Enum):
    SPEED = "speed"
    PORT_TYPE = "port_type"
    MEDIA = "media"
    DISTANCE = "distance"
    MODULE = "module"
    PROTOCOL = "protocol"
    AVAILABILITY = "availability"
    CAPABILITY = "capability"
    REDUNDANCY = "redundancy"
    SAME_RACK = "same_rack"
    PORT_SYMMETRY = "port_symmetry"

@dataclass
class ConstraintResult:
    """约束检查结果"""
    passed: bool
    constraint_type: ConstraintType
    level: ConstraintLevel
    candidate_id: str
    message: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    score_penalty: int = 0

class ConstraintEngine:
    """约束检查引擎"""
    
    def __init__(self):
        self._constraint_handlers = {
            ConstraintType.SPEED: self._check_speed,
            ConstraintType.PORT_TYPE: self._check_port_type,
            ConstraintType.MEDIA: self._check_media,
            ConstraintType.DISTANCE: self._check_distance,
            ConstraintType.MODULE: self._check_module,
            ConstraintType.PROTOCOL: self._check_protocol,
            ConstraintType.AVAILABILITY: self._check_availability,
            ConstraintType.CAPABILITY: self._check_capability,
            ConstraintType.REDUNDANCY: self._check_redundancy,
            ConstraintType.SAME_RACK: self._check_same_rack,
            ConstraintType.PORT_SYMMETRY: self._check_port_symmetry,
        }
    
    async def check_candidate(self, candidate: Candidate, 
                              constraints: List[Dict[str, Any]]) -> ConstraintResult:
        """检查单个候选"""
        results = []
        
        for constraint in constraints:
            constraint_type = constraint.get('type')
            if constraint_type in self._constraint_handlers:
                result = await self._constraint_handlers[constraint_type](
                    candidate, constraint
                )
                results.append(result)
        
        # 所有硬约束必须通过
        hard_failures = [r for r in results if r.level == ConstraintLevel.HARD and not r.passed]
        
        if hard_failures:
            return ConstraintResult(
                passed=False,
                constraint_type=hard_failures[0].constraint_type,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Hard constraint failed: {hard_failures[0].message}",
                details={'failures': [h.details for h in hard_failures]}
            )
        
        # 软约束结果
        soft_failures = [r for r in results if r.level == ConstraintLevel.SOFT and not r.passed]
        total_penalty = sum(r.score_penalty for r in soft_failures)
        
        return ConstraintResult(
            passed=True,
            constraint_type=ConstraintType.AVAILABILITY,
            level=ConstraintLevel.HARD,
            candidate_id=candidate.id,
            message=f"Passed with {len(soft_failures)} soft constraint penalties",
            details={
                'penalties': [f.message for f in soft_failures],
                'total_penalty': total_penalty
            },
            score_penalty=total_penalty
        )
    
    async def check_candidates(self, candidates: List[Candidate],
                               constraints: List[Dict[str, Any]]) -> List[ConstraintResult]:
        """检查多个候选"""
        results = []
        for candidate in candidates:
            result = await self.check_candidate(candidate, constraints)
            results.append(result)
        return results
    
    async def _check_speed(self, candidate: Candidate, 
                          constraint: Dict[str, Any]) -> ConstraintResult:
        """检查速率约束"""
        required_speed = constraint.get('speed', 0)
        candidate_speed = candidate.parameters.get('speed', 0)
        
        if candidate_speed >= required_speed:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.SPEED,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Speed {candidate_speed} >= {required_speed}"
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.SPEED,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Speed {candidate_speed} < {required_speed}"
            )
    
    async def _check_port_type(self, candidate: Candidate,
                               constraint: Dict[str, Any]) -> ConstraintResult:
        """检查端口类型约束"""
        port_type = constraint.get('port_type')
        
        # 获取端口类型
        source_type = candidate.parameters.get('source_port_type')
        target_type = candidate.parameters.get('target_port_type')
        
        if source_type == port_type and target_type == port_type:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.PORT_TYPE,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Port types match: {port_type}"
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.PORT_TYPE,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Port type mismatch: {source_type} != {port_type} or {target_type} != {port_type}"
            )
    
    async def _check_media(self, candidate: Candidate,
                          constraint: Dict[str, Any]) -> ConstraintResult:
        """检查介质约束"""
        allowed_media = constraint.get('media', [])
        candidate_media = candidate.parameters.get('media')
        
        if not allowed_media or candidate_media in allowed_media:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.MEDIA,
                level=ConstraintLevel.SOFT,
                candidate_id=candidate.id,
                message=f"Media {candidate_media} is allowed"
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.MEDIA,
                level=ConstraintLevel.SOFT,
                candidate_id=candidate.id,
                message=f"Media {candidate_media} not in {allowed_media}",
                score_penalty=constraint.get('penalty', 10)
            )
    
    async def _check_distance(self, candidate: Candidate,
                             constraint: Dict[str, Any]) -> ConstraintResult:
        """检查距离约束"""
        max_distance = constraint.get('max_distance', float('inf'))
        candidate_distance = candidate.parameters.get('distance', 0)
        
        if candidate_distance <= max_distance:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.DISTANCE,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Distance {candidate_distance} <= {max_distance}"
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.DISTANCE,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Distance {candidate_distance} > {max_distance}"
            )
    
    async def _check_module(self, candidate: Candidate,
                          constraint: Dict[str, Any]) -> ConstraintResult:
        """检查模块约束"""
        required_module = constraint.get('module')
        candidate_module = candidate.parameters.get('module')
        
        if candidate_module == required_module:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.MODULE,
                level=ConstraintLevel.SOFT,
                candidate_id=candidate.id,
                message=f"Module {candidate_module} matches required"
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.MODULE,
                level=ConstraintLevel.SOFT,
                candidate_id=candidate.id,
                message=f"Module {candidate_module} != {required_module}",
                score_penalty=constraint.get('penalty', 15)
            )
    
    async def _check_protocol(self, candidate: Candidate,
                             constraint: Dict[str, Any]) -> ConstraintResult:
        """检查协议约束"""
        required_protocol = constraint.get('protocol')
        candidate_protocol = candidate.parameters.get('protocol')
        
        if candidate_protocol == required_protocol:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.PROTOCOL,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Protocol {candidate_protocol} matches required"
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.PROTOCOL,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Protocol {candidate_protocol} != {required_protocol}"
            )
    
    async def _check_availability(self, candidate: Candidate,
                                 constraint: Dict[str, Any]) -> ConstraintResult:
        """检查端口可用性"""
        # 检查源端口和目标端口是否可用
        source_available = candidate.parameters.get('source_available', True)
        target_available = candidate.parameters.get('target_available', True)
        
        if source_available and target_available:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.AVAILABILITY,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message="Ports are available"
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.AVAILABILITY,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message="One or more ports are not available"
            )
    
    async def _check_capability(self, candidate: Candidate,
                               constraint: Dict[str, Any]) -> ConstraintResult:
        """检查设备能力"""
        required_capability = constraint.get('capability')
        source_capabilities = candidate.parameters.get('source_capabilities', [])
        target_capabilities = candidate.parameters.get('target_capabilities', [])
        
        if required_capability in source_capabilities and required_capability in target_capabilities:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.CAPABILITY,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Both devices support {required_capability}"
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.CAPABILITY,
                level=ConstraintLevel.HARD,
                candidate_id=candidate.id,
                message=f"Capability {required_capability} not supported by both devices"
            )
    
    async def _check_redundancy(self, candidate: Candidate,
                               constraint: Dict[str, Any]) -> ConstraintResult:
        """检查冗余约束"""
        required_diversity = constraint.get('diversity', [])
        
        # 检查设备多样性
        if 'device' in required_diversity:
            source_device = candidate.source_device_id
            target_device = candidate.target_device_id
            if source_device == target_device:
                return ConstraintResult(
                    passed=False,
                    constraint_type=ConstraintType.REDUNDANCY,
                    level=ConstraintLevel.HARD,
                    candidate_id=candidate.id,
                    message="Device diversity required but same device"
                )
        
        # 检查机柜多样性
        if 'rack' in required_diversity:
            source_rack = candidate.parameters.get('source_rack')
            target_rack = candidate.parameters.get('target_rack')
            if source_rack == target_rack:
                return ConstraintResult(
                    passed=False,
                    constraint_type=ConstraintType.REDUNDANCY,
                    level=ConstraintLevel.HARD,
                    candidate_id=candidate.id,
                    message="Rack diversity required but same rack"
                )
        
        return ConstraintResult(
            passed=True,
            constraint_type=ConstraintType.REDUNDANCY,
            level=ConstraintLevel.HARD,
            candidate_id=candidate.id,
            message="Redundancy requirements satisfied"
        )
    
    async def _check_same_rack(self, candidate: Candidate,
                              constraint: Dict[str, Any]) -> ConstraintResult:
        """检查同机柜约束"""
        source_rack = candidate.parameters.get('source_rack')
        target_rack = candidate.parameters.get('target_rack')
        
        if source_rack == target_rack:
            return ConstraintResult(
                passed=True,
                constraint_type=ConstraintType.SAME_RACK,
                level=ConstraintLevel.SOFT,
                candidate_id=candidate.id,
                message="Same rack",
                score_penalty=0
            )
        else:
            return ConstraintResult(
                passed=False,
                constraint_type=ConstraintType.SAME_RACK,
                level=ConstraintLevel.SOFT,
                candidate_id=candidate.id,
                message="Different racks",
                score_penalty=constraint.get('penalty', 30)
            )
    
    async def _check_port_symmetry(self, candidate: Candidate,
                                  constraint: Dict[str, Any]) -> ConstraintResult:
        """检查端口对称性"""
        source_port = candidate.parameters.get('source_port_name')
        target_port = candidate.parameters.get('target_port_name')
        
        if source_port and target_port:
            # 检查端口名称是否对称 (如 Eth1/1 ↔ Eth1/1)
            if source_port == target_port:
                return ConstraintResult(
                    passed=True,
                    constraint_type=ConstraintType.PORT_SYMMETRY,
                    level=ConstraintLevel.SOFT,
                    candidate_id=candidate.id,
                    message="Ports are symmetric"
                )
        
        return ConstraintResult(
            passed=False,
            constraint_type=ConstraintType.PORT_SYMMETRY,
            level=ConstraintLevel.SOFT,
            candidate_id=candidate.id,
            message="Ports are not symmetric",
            score_penalty=constraint.get('penalty', 10)
        )

## 3. 约束配置

​```python
class ConstraintConfig:
    """约束配置"""
    
    def __init__(self):
        self.hard_constraints = [
            {'type': 'speed', 'speed': 1000},
            {'type': 'port_type', 'port_type': 'ETHERNET'},
            {'type': 'availability'},
            {'type': 'protocol', 'protocol': 'ETHERNET'},
            {'type': 'capability', 'capability': 'fiber'},
        ]
        
        self.soft_constraints = [
            {'type': 'media', 'media': ['SMF'], 'penalty': 10},
            {'type': 'same_rack', 'penalty': 30},
            {'type': 'port_symmetry', 'penalty': 10},
            {'type': 'module', 'module': 'QSFP28', 'penalty': 15},
        ]
    
    def get_all_constraints(self) -> List[Dict[str, Any]]:
        """获取所有约束"""
        return self.hard_constraints + self.soft_constraints
    
    def get_hard_constraints(self) -> List[Dict[str, Any]]:
        """获取硬约束"""
        return self.hard_constraints
    
    def get_soft_constraints(self) -> List[Dict[str, Any]]:
        """获取软约束"""
        return self.soft_constraints

```