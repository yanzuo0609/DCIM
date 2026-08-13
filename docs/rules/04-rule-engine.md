# Rule Engine - 规则匹配与执行引擎

## 1. 引擎架构

┌─────────────────────────────────────────────────────┐
│ Rule Engine │
│ ┌──────────────────────────────────────────────┐ │
│ │ Rule Matcher │ │
│ │ - Condition Evaluation │ │
│ │ - Pattern Matching │ │
│ │ - Expression Evaluation │ │
│ └──────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌──────────────────────────────────────────────┐ │
│ │ Rule Executor │ │
│ │ - Action Execution │ │
│ │ - Constraint Application │ │
│ │ - Scoring Application │ │
│ └──────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌──────────────────────────────────────────────┐ │
│ │ Rule Context │ │
│ │ - Execution Context │ │
│ │ - Variable Resolution │ │
│ │ - State Management │ │
│ └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘

text

```
## 2. 核心实现

​```python
from typing import Dict, Any, List, Optional, Set, Tuple
from dataclasses import dataclass, field
import operator
import re
import json
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

@dataclass
class RuleContext:
    """规则执行上下文"""
    source_device: Optional[Device] = None
    target_device: Optional[Device] = None
    source_port: Optional[Port] = None
    target_port: Optional[Port] = None
    connections: List[Connection] = field(default_factory=list)
    devices: List[Device] = field(default_factory=list)
    ports: List[Port] = field(default_factory=list)
    cables: List[Cable] = field(default_factory=list)
    modules: List[Module] = field(default_factory=list)
    topology: Optional[Topology] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    environment: Dict[str, str] = field(default_factory=dict)
    cache: Dict[str, Any] = field(default_factory=dict)

class RuleMatcher:
    """规则匹配器"""
    
    def __init__(self, repository: RuleRepository):
        self.repository = repository
        self._operators = {
            'eq': operator.eq,
            'ne': operator.ne,
            'gt': operator.gt,
            'gte': operator.ge,
            'lt': operator.lt,
            'lte': operator.le,
            'contains': lambda a, b: b in a,
            'startswith': lambda a, b: a.startswith(b),
            'endswith': lambda a, b: a.endswith(b),
            'matches': lambda a, b: bool(re.match(b, a)),
        }
    
    async def match_rules(self, context: RuleContext) -> List[Rule]:
        """匹配适用的规则"""
        # 获取所有规则
        all_rules = await self.repository.get_by_type("topology")  # 以及其他类型
        matched = []
        
        for rule in all_rules:
            if not rule.enabled:
                continue
            
            if self._matches(rule, context):
                matched.append(rule)
        
        return sorted(matched, key=lambda r: r.priority, reverse=True)
    
    def _matches(self, rule: Rule, context: RuleContext) -> bool:
        """检查规则是否匹配上下文"""
        return self._evaluate_condition(rule.when, context)
    
    def _evaluate_condition(self, condition: Dict[str, Any], context: RuleContext) -> bool:
        """评估条件表达式"""
        for key, value in condition.items():
            if key in ['and', 'and_']:
                if isinstance(value, list):
                    return all(self._evaluate_condition(cond, context) for cond in value)
                else:
                    return self._evaluate_condition(value, context)
            
            elif key in ['or', 'or_']:
                if isinstance(value, list):
                    return any(self._evaluate_condition(cond, context) for cond in value)
                else:
                    return self._evaluate_condition(value, context)
            
            elif key == 'not':
                return not self._evaluate_condition(value, context)
            
            elif key in self._operators:
                op = self._operators[key]
                # 获取左侧值
                left_key = value.get('left') if isinstance(value, dict) else None
                right_val = value.get('right') if isinstance(value, dict) else value
                left_val = self._resolve_variable(left_key, context) if left_key else None
                return op(left_val, right_val) if left_val is not None else False
            
            else:
                # 简单字段匹配
                actual = self._resolve_variable(key, context)
                expected = self._resolve_variable(value, context)
                if actual != expected:
                    return False
        
        return True
    
    def _resolve_variable(self, expr: Any, context: RuleContext) -> Any:
        """解析变量表达式"""
        if isinstance(expr, str):
            # 处理变量引用 ${...}
            if expr.startswith('${') and expr.endswith('}'):
                path = expr[2:-1]
                return self._resolve_path(path, context)
            
            # 处理函数调用
            if expr.startswith('min(') and expr.endswith(')'):
                return self._evaluate_function(expr, context)
        
        return expr
    
    def _resolve_path(self, path: str, context: RuleContext) -> Any:
        """解析路径表达式"""
        parts = path.split('.')
        obj = context
        
        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif isinstance(obj, dict) and part in obj:
                obj = obj[part]
            elif isinstance(obj, list) and part.isdigit():
                obj = obj[int(part)]
            else:
                return None
        
        return obj
    
    def _evaluate_function(self, expr: str, context: RuleContext) -> Any:
        """评估函数调用"""
        # 简单函数实现
        if expr.startswith('min('):
            args = expr[4:-1].split(',')
            values = [self._resolve_variable(arg.strip(), context) for arg in args]
            # 过滤None值
            values = [v for v in values if v is not None]
            return min(values) if values else 0
        
        if expr.startswith('max('):
            args = expr[4:-1].split(',')
            values = [self._resolve_variable(arg.strip(), context) for arg in args]
            values = [v for v in values if v is not None]
            return max(values) if values else 0
        
        return None

class RuleExecutor:
    """规则执行器"""
    
    def __init__(self):
        self.handlers: Dict[str, Callable] = {}
        self._register_default_handlers()
    
    def _register_default_handlers(self) -> None:
        """注册默认处理器"""
        self.handlers['topology'] = self._execute_topology
        self.handlers['redundancy'] = self._execute_redundancy
        self.handlers['media'] = self._execute_media
        self.handlers['security'] = self._execute_security
        self.handlers['allocation'] = self._execute_allocation
    
    async def execute(self, rule: Rule, context: RuleContext) -> Dict[str, Any]:
        """执行规则"""
        handler = self.handlers.get(rule.type)
        if not handler:
            logger.warning(f"No handler for rule type: {rule.type}")
            return {}
        
        try:
            result = await handler(rule, context)
            
            # 应用评分
            if rule.scoring:
                result['scoring'] = self._apply_scoring(rule.scoring, context)
            
            return result
        except Exception as e:
            logger.error(f"Error executing rule {rule.id}: {e}")
            return {'error': str(e)}
    
    async def _execute_topology(self, rule: Rule, context: RuleContext) -> Dict[str, Any]:
        """执行拓扑规则"""
        connection_config = rule.then.get('connection', {})
        
        return {
            'type': 'topology',
            'connection_count': connection_config.get('count', 1),
            'link_type': connection_config.get('link_type', 'UNKNOWN'),
            'constraints': rule.constraints,
            'scoring': rule.scoring,
        }
    
    async def _execute_redundancy(self, rule: Rule, context: RuleContext) -> Dict[str, Any]:
        """执行冗余规则"""
        return {
            'type': 'redundancy',
            'redundancy_type': rule.then.get('redundancy_type', 'ACTIVE_ACTIVE'),
            'diversity': rule.then.get('diversity_requirements', []),
        }
    
    async def _execute_media(self, rule: Rule, context: RuleContext) -> Dict[str, Any]:
        """执行介质规则"""
        return {
            'type': 'media',
            'preferred_cable': rule.then.get('preferred_cable'),
            'fallback': rule.then.get('fallback'),
            'require_module': rule.then.get('require_module', False),
            'module_form_factor': rule.then.get('module_form_factor', []),
        }
    
    async def _execute_security(self, rule: Rule, context: RuleContext) -> Dict[str, Any]:
        """执行安全规则"""
        return {
            'type': 'security',
            'sequence': rule.then.get('sequence', []),
            'firewall_mode': rule.then.get('firewall_mode', 'ACTIVE_STANDBY'),
            'zones': rule.then.get('zones', []),
        }
    
    async def _execute_allocation(self, rule: Rule, context: RuleContext) -> Dict[str, Any]:
        """执行分配规则"""
        return {
            'type': 'allocation',
            'reserve_ports': rule.then.get('reserve_ports', []),
        }
    
    def _apply_scoring(self, scoring: ScoringConfig, context: RuleContext) -> Dict[str, int]:
        """应用评分规则"""
        scores = {}
        
        # 检查每个评分项
        if scoring.same_rack:
            if context.source_device and context.target_device:
                if context.source_device.rack == context.target_device.rack:
                    scores['same_rack'] = scoring.same_rack
        
        if scoring.dac:
            # 检查是否可以使用DAC
            if self._can_use_dac(context):
                scores['dac'] = scoring.dac
        
        if scoring.shortest_path:
            scores['shortest_path'] = self._calculate_shortest_path_score(context)
        
        return scores
    
    def _can_use_dac(self, context: RuleContext) -> bool:
        """检查是否可以使用DAC"""
        # 检查距离、速率等
        distance = context.parameters.get('distance', 0)
        speed = context.parameters.get('speed', 0)
        
        # DAC适用于短距离、高速率
        return distance <= 7 and speed >= 10000
    
    def _calculate_shortest_path_score(self, context: RuleContext) -> int:
        """计算最短路径评分"""
        # 简化实现
        distance = context.parameters.get('distance', 0)
        if distance < 10:
            return 15
        elif distance < 50:
            return 10
        elif distance < 100:
            return 5
        return 0

class RuleEngine:
    """规则引擎主类"""
    
    def __init__(self, repository: RuleRepository):
        self.repository = repository
        self.matcher = RuleMatcher(repository)
        self.executor = RuleExecutor()
        self.context = RuleContext()
    
    async def process(self, context: RuleContext) -> List[Dict[str, Any]]:
        """处理规则"""
        self.context = context
        
        # 1. 匹配规则
        matched_rules = await self.matcher.match_rules(context)
        
        if not matched_rules:
            logger.warning("No matching rules found")
            return []
        
        # 2. 执行规则
        results = []
        for rule in matched_rules:
            result = await self.executor.execute(rule, context)
            result['rule_id'] = rule.id
            result['rule_name'] = rule.name
            results.append(result)
        
        # 3. 冲突解决
        resolved = self._resolve_conflicts(results)
        
        return resolved
    
    def _resolve_conflicts(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """解决规则结果冲突"""
        # 按优先级排序
        sorted_results = sorted(results, key=lambda r: r.get('priority', 0), reverse=True)
        
        # 检测冲突
        conflicts = self._detect_conflicts(sorted_results)
        
        if conflicts:
            logger.warning(f"Detected {len(conflicts)} rule conflicts")
        
        return sorted_results
    
    def _detect_conflicts(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """检测规则冲突"""
        conflicts = []
        seen = set()
        
        for result in results:
            # 检查是否已有相同类型的规则结果
            result_type = result.get('type')
            if result_type in seen:
                conflicts.append({
                    'type': result_type,
                    'rules': [r for r in results if r.get('type') == result_type]
                })
            seen.add(result_type)
        
        return conflicts
    
    async def explain(self, result: Dict[str, Any]) -> str:
        """解释规则执行结果"""
        return f"Rule '{result.get('rule_name', result.get('rule_id'))}' applied with type {result.get('type')}"
```