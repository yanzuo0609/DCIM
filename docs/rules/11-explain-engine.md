# Explain Engine - 解释引擎

## 1. 功能概述

解释引擎为每个连接决策提供可读的解释，帮助用户理解为什么选择这个连接方案。

## 2. 解释内容

1. 使用的规则
2. 约束满足情况
3. 评分明细
4. 优化原因
5. 替代方案

## 3. 解释器实现

```python
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class Explanation:
    """解释结果"""
    connection_id: str
    summary: str
    rule_explanation: str
    constraint_explanation: str
    scoring_explanation: str
    optimization_explanation: Optional[str] = None
    alternatives: List[str] = field(default_factory=list)
    generated_at: datetime = field(default_factory=datetime.now)

class ExplainEngine:
    """解释引擎"""
    
    def __init__(self):
        self._template_engine = TemplateEngine()
    
    async def explain_connection(self, connection: Connection,
                                context: Dict[str, Any]) -> Explanation:
        """生成连接解释"""
        # 获取规则解释
        rule_explanation = await self._explain_rule(connection, context)
        
        # 获取约束解释
        constraint_explanation = await self._explain_constraints(connection, context)
        
        # 获取评分解释
        scoring_explanation = await self._explain_scoring(connection, context)
        
        # 获取优化解释
        optimization_explanation = await self._explain_optimization(connection, context)
        
        # 生成替代方案
        alternatives = await self._generate_alternatives(connection, context)
        
        # 生成摘要
        summary = self._generate_summary(connection, context)
        
        return Explanation(
            connection_id=connection.id,
            summary=summary,
            rule_explanation=rule_explanation,
            constraint_explanation=constraint_explanation,
            scoring_explanation=scoring_explanation,
            optimization_explanation=optimization_explanation,
            alternatives=alternatives
        )
    
    async def explain_batch(self, connections: List[Connection],
                           context: Dict[str, Any]) -> List[Explanation]:
        """批量生成解释"""
        explanations = []
        for connection in connections:
            explanation = await self.explain_connection(connection, context)
            explanations.append(explanation)
        return explanations
    
    async def _explain_rule(self, connection: Connection,
                           context: Dict[str, Any]) -> str:
        """解释规则"""
        rule_id = connection.rule_id
        if not rule_id:
            return "No specific rule was applied."
        
        rule = context.get('rules', {}).get(rule_id)
        if not rule:
            return f"Rule {rule_id} was applied but details are not available."
        
        return f"Rule '{rule.name}' (ID: {rule_id}) was applied because the connection matched the conditions: {self._format_conditions(rule.when)}"
    
    async def _explain_constraints(self, connection: Connection,
                                  context: Dict[str, Any]) -> str:
        """解释约束"""
        constraints = context.get('constraints', [])
        satisfied = context.get('satisfied_constraints', [])
        unsatisfied = context.get('unsatisfied_constraints', [])
        
        parts = []
        
        if satisfied:
            parts.append(f"Satisfied constraints: {', '.join(satisfied)}")
        
        if unsatisfied:
            parts.append(f"Note: Some constraints were relaxed: {', '.join(unsatisfied)}")
        
        if not parts:
            return "All constraints were satisfied."
        
        return "; ".join(parts)
    
    async def _explain_scoring(self, connection: Connection,
                              context: Dict[str, Any]) -> str:
        """解释评分"""
        score_breakdown = connection.score_breakdown
        total_score = connection.score
        
        if not score_breakdown:
            return f"Total score: {total_score}"
        
        parts = []
        for factor, score in score_breakdown.items():
            if score > 0:
                parts.append(f"{factor}: {score}")
        
        return f"Total score {total_score} from: {', '.join(parts)}"
    
    async def _explain_optimization(self, connection: Connection,
                                   context: Dict[str, Any]) -> Optional[str]:
        """解释优化"""
        optimization_details = context.get('optimization_details')
        if not optimization_details:
            return None
        
        return f"Selected as part of global optimization to achieve: {optimization_details}"
    
    async def _generate_alternatives(self, connection: Connection,
                                    context: Dict[str, Any]) -> List[str]:
        """生成替代方案"""
        alternatives = context.get('alternatives', [])
        return [f"Alternative {i+1}: {alt}" for i, alt in enumerate(alternatives[:5])]
    
    def _generate_summary(self, connection: Connection,
                         context: Dict[str, Any]) -> str:
        """生成摘要"""
        source = connection.source
        destination = connection.destination
        
        return f"Connection from {source.device_name}:{source.port_name} to {destination.device_name}:{destination.port_name} using {connection.cable.type if connection.cable else 'unknown cable'}"
    
    def _format_conditions(self, conditions: Dict[str, Any]) -> str:
        """格式化条件"""
        parts = []
        for key, value in conditions.items():
            if key in ['and', 'or', 'not']:
                continue
            parts.append(f"{key}={value}")
        return ", ".join(parts)

class TemplateEngine:
    """模板引擎"""
    
    def __init__(self):
        self.templates = {}
        self._load_templates()
    
    def _load_templates(self) -> None:
        """加载模板"""
        self.templates = {
            'success': "✅ Connection {id} was successfully generated.",
            'warning': "⚠️ Connection {id} has warnings: {warnings}",
            'error': "❌ Connection {id} has errors: {errors}",
            'summary': "📊 {type} connection from {source} to {destination}",
            'score': "📈 Score: {score} ({breakdown})",
            'rule': "📋 Rule: {rule}",
            'constraint': "🔒 Constraints: {constraints}",
        }
    
    def render(self, template_name: str, **kwargs) -> str:
        """渲染模板"""
        template = self.templates.get(template_name, "")
        return template.format(**kwargs)
```