# Scoring Engine - 评分引擎

## 1. 评分架构

┌─────────────────────────────────────────────────────┐
│ Scoring Engine │
│ ┌──────────────────────────────────────────────┐ │
│ │ Score Calculator │ │
│ │ - Individual Score Computation │ │
│ │ - Weighted Scoring │ │
│ │ - Multi-factor Evaluation │ │
│ └──────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌──────────────────────────────────────────────┐ │
│ │ Score Aggregator │ │
│ │ - Score Summation │ │
│ │ - Weighted Average │ │
│ │ - Normalization │ │
│ └──────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌──────────────────────────────────────────────┐ │
│ │ Score Ranker │ │
│ │ - Ranking by Score │ │
│ │ - Tie-breaking │ │
│ │ - Score Distribution │ │
│ └──────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘

text

```
## 2. 评分因子

| 评分项 | 默认权重 | 说明 |
|--------|---------|------|
| 同机柜 | 30 | 同一机柜内连接 |
| DAC线缆 | 20 | 使用DAC直连铜缆 |
| 预留端口 | 20 | 使用预留端口 |
| 最短路径 | 15 | 物理路径最短 |
| 速率匹配 | 10 | 端口速率精确匹配 |
| 端口角色匹配 | 10 | 端口角色匹配 |
| 设备多样性 | 20 | 不同设备连接 |
| 机柜多样性 | 10 | 不同机柜连接 |
| 端口对称性 | 10 | 端口号对称 |
| 模块兼容性 | 15 | 模块完全兼容 |

## 3. 评分计算器

​```python
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging

logger = logging.getLogger(__name__)

@dataclass
class ScoreBreakdown:
    """评分明细"""
    factor_name: str
    score: int
    weight: int = 1
    details: Optional[str] = None

@dataclass
class ScoreResult:
    """评分结果"""
    candidate_id: str
    total_score: int
    breakdown: List[ScoreBreakdown]
    normalized_score: float = 0.0
    rank: Optional[int] = None

class ScoringEngine:
    """评分引擎"""
    
    def __init__(self):
        self._score_factors = [
            self._score_same_rack,
            self._score_dac,
            self._score_reserved_port,
            self._score_shortest_path,
            self._score_speed_match,
            self._score_port_role_match,
            self._score_device_diversity,
            self._score_rack_diversity,
            self._score_port_symmetry,
            self._score_module_compatibility,
        ]
    
    async def score_candidate(self, candidate: Candidate, 
                             context: Dict[str, Any]) -> ScoreResult:
        """对单个候选进行评分"""
        breakdown = []
        total_score = 0
        
        for factor in self._score_factors:
            score, details = await factor(candidate, context)
            if score > 0:
                breakdown.append(ScoreBreakdown(
                    factor_name=factor.__name__.replace('_score_', ''),
                    score=score,
                    details=details
                ))
                total_score += score
        
        return ScoreResult(
            candidate_id=candidate.id,
            total_score=total_score,
            breakdown=breakdown
        )
    
    async def score_candidates(self, candidates: List[Candidate],
                              context: Dict[str, Any]) -> List[ScoreResult]:
        """对多个候选进行评分"""
        results = []
        for candidate in candidates:
            result = await self.score_candidate(candidate, context)
            results.append(result)
        
        # 归一化和排名
        max_score = max(r.total_score for r in results) if results else 0
        for result in results:
            result.normalized_score = result.total_score / max_score if max_score > 0 else 0
        
        # 排序
        sorted_results = sorted(results, key=lambda r: r.total_score, reverse=True)
        for i, result in enumerate(sorted_results):
            result.rank = i + 1
        
        return sorted_results
    
    async def _score_same_rack(self, candidate: Candidate,
                               context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """同机柜评分"""
        source_rack = context.get('source_device', {}).get('rack')
        target_rack = context.get('target_device', {}).get('rack')
        
        if source_rack and target_rack and source_rack == target_rack:
            return 30, f"Same rack: {source_rack}"
        return 0, None
    
    async def _score_dac(self, candidate: Candidate,
                        context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """DAC线缆评分"""
        distance = context.get('distance', 0)
        speed = context.get('speed', 0)
        
        # DAC适用于短距离高速率
        if distance <= 7 and speed >= 10000:
            return 20, f"DAC suitable: {distance}m, {speed}Mbps"
        return 0, None
    
    async def _score_reserved_port(self, candidate: Candidate,
                                  context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """预留端口评分"""
        source_port = context.get('source_port')
        target_port = context.get('target_port')
        
        score = 0
        details = []
        
        if source_port and source_port.status == PortStatus.RESERVED:
            score += 10
            details.append("Source port reserved")
        if target_port and target_port.status == PortStatus.RESERVED:
            score += 10
            details.append("Target port reserved")
        
        return score, ", ".join(details) if details else None
    
    async def _score_shortest_path(self, candidate: Candidate,
                                  context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """最短路径评分"""
        distance = context.get('distance', 0)
        
        if distance < 10:
            return 15, f"Very short path: {distance}m"
        elif distance < 50:
            return 10, f"Short path: {distance}m"
        elif distance < 100:
            return 5, f"Medium path: {distance}m"
        return 0, None
    
    async def _score_speed_match(self, candidate: Candidate,
                                context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """速率匹配评分"""
        source_speed = context.get('source_speed', 0)
        target_speed = context.get('target_speed', 0)
        
        if source_speed == target_speed:
            return 10, f"Exact speed match: {source_speed}Mbps"
        elif source_speed in context.get('supported_speeds', []):
            return 5, f"Compatible speed: {source_speed}Mbps"
        return 0, None
    
    async def _score_port_role_match(self, candidate: Candidate,
                                    context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """端口角色匹配评分"""
        source_role = context.get('source_port_role')
        target_role = context.get('target_port_role')
        
        compatible_pairs = {
            (PortRole.UPLINK, PortRole.DOWNLINK): 10,
            (PortRole.DOWNLINK, PortRole.UPLINK): 10,
            (PortRole.PEER_LINK, PortRole.PEER_LINK): 10,
            (PortRole.SERVER, PortRole.DOWNLINK): 10,
            (PortRole.DOWNLINK, PortRole.SERVER): 10,
        }
        
        score = compatible_pairs.get((source_role, target_role), 0)
        if score > 0:
            return score, f"Role match: {source_role} ↔ {target_role}"
        return 0, None
    
    async def _score_device_diversity(self, candidate: Candidate,
                                     context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """设备多样性评分"""
        source_device = context.get('source_device')
        target_device = context.get('target_device')
        
        if source_device and target_device and source_device.id != target_device.id:
            return 20, f"Device diversity: {source_device.id} ≠ {target_device.id}"
        return 0, None
    
    async def _score_rack_diversity(self, candidate: Candidate,
                                   context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """机柜多样性评分"""
        source_rack = context.get('source_device', {}).get('rack')
        target_rack = context.get('target_device', {}).get('rack')
        
        if source_rack and target_rack and source_rack != target_rack:
            return 10, f"Rack diversity: {source_rack} ≠ {target_rack}"
        return 0, None
    
    async def _score_port_symmetry(self, candidate: Candidate,
                                  context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """端口对称性评分"""
        source_port_name = context.get('source_port_name')
        target_port_name = context.get('target_port_name')
        
        if source_port_name and target_port_name and source_port_name == target_port_name:
            return 10, f"Port symmetry: {source_port_name}"
        return 0, None
    
    async def _score_module_compatibility(self, candidate: Candidate,
                                        context: Dict[str, Any]) -> Tuple[int, Optional[str]]:
        """模块兼容性评分"""
        source_module = context.get('source_module')
        target_module = context.get('target_module')
        
        if source_module and target_module:
            # 检查模块兼容性
            if source_module.part_number == target_module.part_number:
                return 15, f"Module compatibility: {source_module.part_number}"
            elif source_module.form_factor == target_module.form_factor:
                return 10, f"Module form factor match: {source_module.form_factor}"
            else:
                return 5, "Module basic compatibility"
        return 0, None

## 4. 权重配置

​```python
class ScoreWeights:
    """评分权重配置"""
    
    def __init__(self, weights: Optional[Dict[str, int]] = None):
        self.weights = weights or {
            'same_rack': 30,
            'dac': 20,
            'reserved_port': 20,
            'shortest_path': 15,
            'speed_match': 10,
            'port_role_match': 10,
            'device_diversity': 20,
            'rack_diversity': 10,
            'port_symmetry': 10,
            'module_compatibility': 15,
        }
    
    def get_weight(self, factor_name: str) -> int:
        """获取权重"""
        return self.weights.get(factor_name, 0)
    
    def update_weight(self, factor_name: str, weight: int) -> None:
        """更新权重"""
        self.weights[factor_name] = weight
```