# Rule Conflict - 规则冲突检测与解决

## 1. 冲突类型

| 类型 | 说明 | 示例 |
|------|------|------|
| 规则冲突 | 多条规则产生矛盾结果 | 一条规则要求DAC，另一条要求光纤 |
| 约束冲突 | 不同约束产生矛盾 | 硬约束和软约束冲突 |
| 资源冲突 | 资源分配冲突 | 两个连接争夺同一个端口 |
| 评分冲突 | 评分目标冲突 | 成本最优 vs 性能最优 |

## 2. 冲突检测与解决

```python
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

class ConflictType(str, Enum):
    RULE = "rule"
    CONSTRAINT = "constraint"
    RESOURCE = "resource"
    SCORING = "scoring"

@dataclass
class Conflict:
    """冲突"""
    type: ConflictType
    description: str
    items: List[Any]
    resolution: Optional[str] = None
    severity: str = "MEDIUM"

class RuleConflictDetector:
    """规则冲突检测器"""
    
    def __init__(self):
        self._detectors = {
            'rule': self._detect_rule_conflicts,
            'constraint': self._detect_constraint_conflicts,
            'resource': self._detect_resource_conflicts,
            'scoring': self._detect_scoring_conflicts,
        }
    
    async def detect_conflicts(self, rules: List[Rule],
                              candidates: List[Candidate],
                              connections: List[Connection]) -> List[Conflict]:
        """检测所有冲突"""
        all_conflicts = []
        
        for conflict_type, detector in self._detectors.items():
            conflicts = await detector(rules, candidates, connections)
            all_conflicts.extend(conflicts)
        
        return all_conflicts
    
    async def _detect_rule_conflicts(self, rules: List[Rule],
                                    candidates: List[Candidate],
                                    connections: List[Connection]) -> List[Conflict]:
        """检测规则冲突"""
        conflicts = []
        
        # 按类型分组规则
        rules_by_type: Dict[str, List[Rule]] = {}
        for rule in rules:
            if rule.type not in rules_by_type:
                rules_by_type[rule.type] = []
            rules_by_type[rule.type].append(rule)
        
        # 检查同类型规则是否有冲突
        for rule_type, type_rules in rules_by_type.items():
            if len(type_rules) > 1:
                # 检查规则条件是否重叠
                for i, rule1 in enumerate(type_rules):
                    for rule2 in type_rules[i+1:]:
                        if self._rules_overlap(rule1, rule2):
                            conflicts.append(Conflict(
                                type=ConflictType.RULE,
                                description=f"Rules {rule1.id} and {rule2.id} overlap",
                                items=[rule1, rule2],
                                severity="HIGH"
                            ))
        
        return conflicts
    
    def _rules_overlap(self, rule1: Rule, rule2: Rule) -> bool:
        """检查规则是否重叠"""
        # 简化实现：检查是否有相同的条件
        for key, value in rule1.when.items():
            if key in rule2.when and rule2.when[key] == value:
                return True
        return False
    
    async def _detect_constraint_conflicts(self, rules: List[Rule],
                                          candidates: List[Candidate],
                                          connections: List[Connection]) -> List[Conflict]:
        """检测约束冲突"""
        conflicts = []
        
        # 获取所有约束
        all_constraints = []
        for rule in rules:
            all_constraints.extend(rule.constraints)
        
        # 检查硬约束和软约束是否冲突
        hard_constraints = [c for c in all_constraints if c.get('level') == 'hard']
        soft_constraints = [c for c in all_constraints if c.get('level') == 'soft']
        
        for hard in hard_constraints:
            for soft in soft_constraints:
                if self._constraints_conflict(hard, soft):
                    conflicts.append(Conflict(
                        type=ConflictType.CONSTRAINT,
                        description=f"Hard constraint {hard} conflicts with soft constraint {soft}",
                        items=[hard, soft],
                        severity="HIGH"
                    ))
        
        return conflicts
    
    def _constraints_conflict(self, constraint1: Dict, constraint2: Dict) -> bool:
        """检查约束是否冲突"""
        # 检查是否对同一属性有不同要求
        if constraint1.get('type') == constraint2.get('type'):
            if constraint1.get('type') == 'speed':
                if constraint1.get('speed') != constraint2.get('speed'):
                    return True
            elif constraint1.get('type') == 'media':
                media1 = set(constraint1.get('media', []))
                media2 = set(constraint2.get('media', []))
                if not media1.intersection(media2):
                    return True
        return False
    
    async def _detect_resource_conflicts(self, rules: List[Rule],
                                        candidates: List[Candidate],
                                        connections: List[Connection]) -> List[Conflict]:
        """检测资源冲突"""
        conflicts = []
        
        # 检查端口冲突
        used_ports: Dict[str, str] = {}  # port_id -> connection_id
        for connection in connections:
            if connection.source.port_id:
                if connection.source.port_id in used_ports:
                    conflicts.append(Conflict(
                        type=ConflictType.RESOURCE,
                        description=f"Port {connection.source.port_id} used by multiple connections",
                        items=[connection, used_ports[connection.source.port_id]],
                        severity="CRITICAL"
                    ))
                else:
                    used_ports[connection.source.port_id] = connection.id
            
            if connection.destination.port_id:
                if connection.destination.port_id in used_ports:
                    conflicts.append(Conflict(
                        type=ConflictType.RESOURCE,
                        description=f"Port {connection.destination.port_id} used by multiple connections",
                        items=[connection, used_ports[connection.destination.port_id]],
                        severity="CRITICAL"
                    ))
                else:
                    used_ports[connection.destination.port_id] = connection.id
        
        return conflicts
    
    async def _detect_scoring_conflicts(self, rules: List[Rule],
                                       candidates: List[Candidate],
                                       connections: List[Connection]) -> List[Conflict]:
        """检测评分冲突"""
        conflicts = []
        
        # 检查是否有规则评分方向相反
        for rule1 in rules:
            for rule2 in rules:
                if rule1.id >= rule2.id:
                    continue
                
                if self._scoring_conflicts(rule1, rule2):
                    conflicts.append(Conflict(
                        type=ConflictType.SCORING,
                        description=f"Scoring conflicts between {rule1.id} and {rule2.id}",
                        items=[rule1, rule2],
                        severity="MEDIUM"
                    ))
        
        return conflicts
    
    def _scoring_conflicts(self, rule1: Rule, rule2: Rule) -> bool:
        """检查评分是否冲突"""
        if not rule1.scoring or not rule2.scoring:
            return False
        
        # 检查是否有相同的评分项但不同权重
        for field in rule1.scoring.dict():
            if hasattr(rule2.scoring, field):
                value1 = getattr(rule1.scoring, field)
                value2 = getattr(rule2.scoring, field)
                if value1 and value2 and value1 != value2:
                    return True
        
        return False

class ConflictResolver:
    """冲突解决器"""
    
    def __init__(self):
        self._strategies = {
            ConflictType.RULE: self._resolve_rule_conflict,
            ConflictType.CONSTRAINT: self._resolve_constraint_conflict,
            ConflictType.RESOURCE: self._resolve_resource_conflict,
            ConflictType.SCORING: self._resolve_scoring_conflict,
        }
    
    async def resolve_conflict(self, conflict: Conflict) -> Any:
        """解决冲突"""
        strategy = self._strategies.get(conflict.type)
        if strategy:
            return await strategy(conflict)
        return None
    
    async def resolve_conflicts(self, conflicts: List[Conflict]) -> List[Dict[str, Any]]:
        """解决所有冲突"""
        results = []
        
        for conflict in conflicts:
            result = await self.resolve_conflict(conflict)
            if result:
                results.append(result)
        
        return results
    
    async def _resolve_rule_conflict(self, conflict: Conflict) -> Dict[str, Any]:
        """解决规则冲突"""
        # 按优先级选择
        rules = conflict.items
        selected = max(rules, key=lambda r: getattr(r, 'priority', 0))
        
        return {
            'action': 'select_highest_priority',
            'selected_rule': selected.id,
            'rules': [r.id for r in rules]
        }
    
    async def _resolve_constraint_conflict(self, conflict: Conflict) -> Dict[str, Any]:
        """解决约束冲突"""
        # 硬约束优先于软约束
        items = conflict.items
        hard = [i for i in items if i.get('level') == 'hard']
        soft = [i for i in items if i.get('level') == 'soft']
        
        if hard and soft:
            return {
                'action': 'hard_constraint_wins',
                'selected': hard[0],
                'rejected': soft[0]
            }
        
        return {
            'action': 'no_resolution',
            'items': items
        }
    
    async def _resolve_resource_conflict(self, conflict: Conflict) -> Dict[str, Any]:
        """解决资源冲突"""
        items = conflict.items
        
        # 保留最早分配的
        return {
            'action': 'first_assignment_wins',
            'retained': items[0].id,
            'rejected': items[1].id if len(items) > 1 else None
        }
    
    async def _resolve_scoring_conflict(self, conflict: Conflict) -> Dict[str, Any]:
        """解决评分冲突"""
        items = conflict.items
        
        # 取平均权重
        return {
            'action': 'average_weights',
            'items': [i.id for i in items]
        }
```