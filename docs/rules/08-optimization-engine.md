# Optimization Engine - 全局优化引擎

## 1. 优化目标

1. **负载均衡**：均匀分布连接，避免单个设备过载
2. **资源利用**：最大化端口利用率
3. **路径优化**：最小化总体路径长度
4. **成本优化**：最小化线缆和模块成本
5. **冗余保障**：确保满足冗余要求

## 2. 优化算法

```python
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
import numpy as np
from scipy.optimize import linear_sum_assignment
import networkx as nx
import logging

logger = logging.getLogger(__name__)

@dataclass
class OptimizationResult:
    """优化结果"""
    selected_candidates: List[str]  # 选中的候选ID
    total_score: float
    resource_utilization: Dict[str, float]
    constraints_satisfied: bool
    objective_value: float
    details: Dict[str, Any] = field(default_factory=dict)

class OptimizationEngine:
    """全局优化引擎"""
    
    def __init__(self, max_iterations: int = 1000):
        self.max_iterations = max_iterations
        self._graph = nx.Graph()
    
    async def optimize(self, candidates: List[Candidate],
                       score_results: List[ScoreResult],
                       constraints: Dict[str, Any]) -> OptimizationResult:
        """执行全局优化"""
        logger.info(f"Optimizing {len(candidates)} candidates")
        
        # 构建优化模型
        model = self._build_optimization_model(candidates, score_results, constraints)
        
        # 求解
        solution = await self._solve(model)
        
        # 构建结果
        return self._build_result(solution, candidates, score_results)
    
    def _build_optimization_model(self, candidates: List[Candidate],
                                  score_results: List[ScoreResult],
                                  constraints: Dict[str, Any]) -> Dict[str, Any]:
        """构建优化模型"""
        n = len(candidates)
        
        # 构建评分矩阵
        scores = np.zeros(n)
        for i, result in enumerate(score_results):
            scores[i] = result.total_score
        
        # 构建约束矩阵
        constraints_matrix = self._build_constraints_matrix(candidates, constraints)
        
        return {
            'n': n,
            'scores': scores,
            'constraints': constraints_matrix,
            'required_connections': constraints.get('required_connections', len(candidates) // 2)
        }
    
    def _build_constraints_matrix(self, candidates: List[Candidate],
                                 constraints: Dict[str, Any]) -> np.ndarray:
        """构建约束矩阵"""
        n = len(candidates)
        constraints_matrix = np.zeros((n, n))
        
        # 设备容量约束
        device_capacity = constraints.get('device_capacity', {})
        for i, candidate in enumerate(candidates):
            source_device = candidate.source_device_id
            target_device = candidate.target_device_id
            
            if source_device in device_capacity:
                constraints_matrix[i, i] = device_capacity[source_device]
            
            if target_device in device_capacity:
                constraints_matrix[i, i] = min(constraints_matrix[i, i], 
                                              device_capacity[target_device])
        
        return constraints_matrix
    
    async def _solve(self, model: Dict[str, Any]) -> np.ndarray:
        """求解优化问题"""
        n = model['n']
        scores = model['scores']
        constraints = model['constraints']
        required = model['required_connections']
        
        # 使用匈牙利算法求解
        cost_matrix = -scores.reshape(1, -1)
        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        
        # 构建选择向量
        selected = np.zeros(n, dtype=bool)
        for i in col_ind:
            if i < n:
                selected[i] = True
        
        # 确保满足连接数量要求
        if np.sum(selected) < required:
            # 选择更多候选
            remaining = sorted([(i, scores[i]) for i in range(n) if not selected[i]], 
                             key=lambda x: x[1], reverse=True)
            for i, _ in remaining[:required - np.sum(selected)]:
                selected[i] = True
        
        return selected
    
    def _build_result(self, solution: np.ndarray,
                     candidates: List[Candidate],
                     score_results: List[ScoreResult]) -> OptimizationResult:
        """构建优化结果"""
        selected_ids = []
        total_score = 0
        utilization = {}
        
        for i, selected in enumerate(solution):
            if selected and i < len(candidates):
                candidate = candidates[i]
                selected_ids.append(candidate.id)
                total_score += score_results[i].total_score
                
                # 计算资源利用率
                source_device = candidate.source_device_id
                if source_device not in utilization:
                    utilization[source_device] = 0
                utilization[source_device] += 1
        
        return OptimizationResult(
            selected_candidates=selected_ids,
            total_score=total_score,
            resource_utilization=utilization,
            constraints_satisfied=True,
            objective_value=total_score,
            details={
                'solution_size': len(selected_ids),
                'candidate_count': len(candidates)
            }
        )

class LoadBalancingOptimizer:
    """负载均衡优化器"""
    
    def __init__(self, max_ports_per_device: int = 48):
        self.max_ports_per_device = max_ports_per_device
    
    async def optimize(self, candidates: List[Candidate],
                      score_results: List[ScoreResult]) -> List[Candidate]:
        """优化负载均衡"""
        # 按设备分组候选
        device_candidates = {}
        for candidate in candidates:
            device_id = candidate.source_device_id
            if device_id not in device_candidates:
                device_candidates[device_id] = []
            device_candidates[device_id].append(candidate)
        
        # 限制每个设备的候选数量
        selected = []
        for device_id, device_cands in device_candidates.items():
            # 按分数排序
            device_cands = sorted(device_cands, 
                                key=lambda c: self._get_score(c.id, score_results),
                                reverse=True)
            # 取前N个
            limit = min(len(device_cands), self.max_ports_per_device)
            selected.extend(device_cands[:limit])
        
        return selected
    
    def _get_score(self, candidate_id: str, 
                   score_results: List[ScoreResult]) -> float:
        """获取候选分数"""
        for result in score_results:
            if result.candidate_id == candidate_id:
                return result.total_score
        return 0

class PathOptimizer:
    """路径优化器"""
    
    def __init__(self, max_path_length: float = 100.0):
        self.max_path_length = max_path_length
    
    async def optimize(self, candidates: List[Candidate],
                      paths: Dict[str, float]) -> List[Candidate]:
        """优化路径长度"""
        selected = []
        for candidate in candidates:
            path_length = paths.get(candidate.id, float('inf'))
            if path_length <= self.max_path_length:
                selected.append(candidate)
        
        return sorted(selected, key=lambda c: paths.get(c.id, float('inf')))

class CostOptimizer:
    """成本优化器"""
    
    def __init__(self, cable_cost_per_meter: float = 1.0,
                 module_cost: float = 100.0):
        self.cable_cost_per_meter = cable_cost_per_meter
        self.module_cost = module_cost
    
    async def optimize(self, candidates: List[Candidate],
                      context: Dict[str, Any]) -> List[Candidate]:
        """优化成本"""
        costed_candidates = []
        
        for candidate in candidates:
            # 计算线缆成本
            distance = context.get('distance', 0)
            cable_cost = distance * self.cable_cost_per_meter
            
            # 计算模块成本
            source_module = context.get('source_module')
            target_module = context.get('target_module')
            module_cost = (1 if source_module else 0) * self.module_cost + \
                         (1 if target_module else 0) * self.module_cost
            
            total_cost = cable_cost + module_cost
            
            costed_candidates.append((candidate, total_cost))
        
        # 按成本排序
        costed_candidates.sort(key=lambda x: x[1])
        
        return [c for c, _ in costed_candidates]
```