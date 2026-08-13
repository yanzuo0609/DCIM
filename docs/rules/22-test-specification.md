# Test Specification - 测试规范

## 1. 测试架构

markdown

```
# Test Specification - 测试规范

## 1. 测试架构
```



tests/
├── unit/
│ ├── domain/
│ ├── dsl/
│ ├── engine/
│ ├── repository/
│ └── utils/
├── integration/
│ ├── engine/
│ ├── repository/
│ └── api/
├── scenario/
│ ├── three_tier/
│ ├── spine_leaf/
│ └── security/
└── regression/
└── known_issues/

text

```
## 2. 单元测试

​```python
# tests/unit/engine/test_constraint_engine.py
import pytest
from datetime import datetime
from src.engine.constraint import ConstraintEngine, ConstraintType, ConstraintLevel
from src.domain.models import Device, Port, Candidate

class TestConstraintEngine:
    """约束引擎测试"""
    
    @pytest.fixture
    def constraint_engine(self):
        return ConstraintEngine()
    
    @pytest.fixture
    def sample_candidate(self):
        return Candidate(
            id="candidate-1",
            source_device_id="device-1",
            source_port_id="port-1",
            target_device_id="device-2",
            target_port_id="port-2",
            match_type="all_to_all",
            parameters={
                'speed': 10000,
                'media': 'SMF',
                'distance': 50
            }
        )
    
    def test_speed_constraint_pass(self, constraint_engine, sample_candidate):
        """测试速率约束通过"""
        constraint = {
            'type': 'speed',
            'speed': 10000,
            'level': 'hard'
        }
        
        result = constraint_engine._check_speed(sample_candidate, constraint)
        assert result.passed is True
        assert result.level == ConstraintLevel.HARD
    
    def test_speed_constraint_fail(self, constraint_engine, sample_candidate):
        """测试速率约束失败"""
        constraint = {
            'type': 'speed',
            'speed': 40000,
            'level': 'hard'
        }
        
        result = constraint_engine._check_speed(sample_candidate, constraint)
        assert result.passed is False
        assert result.level == ConstraintLevel.HARD
    
    def test_media_constraint_pass(self, constraint_engine, sample_candidate):
        """测试介质约束通过"""
        constraint = {
            'type': 'media',
            'media': ['SMF', 'MMF'],
            'level': 'soft',
            'penalty': 10
        }
        
        result = constraint_engine._check_media(sample_candidate, constraint)
        assert result.passed is True
        assert result.level == ConstraintLevel.SOFT
        assert result.score_penalty == 0
    
    def test_media_constraint_fail(self, constraint_engine, sample_candidate):
        """测试介质约束失败"""
        constraint = {
            'type': 'media',
            'media': ['DAC'],
            'level': 'soft',
            'penalty': 10
        }
        
        result = constraint_engine._check_media(sample_candidate, constraint)
        assert result.passed is False
        assert result.level == ConstraintLevel.SOFT
        assert result.score_penalty == 10
    
    def test_distance_constraint_pass(self, constraint_engine, sample_candidate):
        """测试距离约束通过"""
        constraint = {
            'type': 'distance',
            'max_distance': 100,
            'level': 'hard'
        }
        
        result = constraint_engine._check_distance(sample_candidate, constraint)
        assert result.passed is True
    
    def test_distance_constraint_fail(self, constraint_engine, sample_candidate):
        """测试距离约束失败"""
        constraint = {
            'type': 'distance',
            'max_distance': 10,
            'level': 'hard'
        }
        
        result = constraint_engine._check_distance(sample_candidate, constraint)
        assert result.passed is False

# tests/unit/engine/test_scoring_engine.py
class TestScoringEngine:
    """评分引擎测试"""
    
    @pytest.fixture
    def scoring_engine(self):
        return ScoringEngine()
    
    @pytest.fixture
    def sample_context(self):
        return {
            'source_device': Device(id='d1', name='SW1', role=DeviceRole.CORE_SWITCH, rack='R1'),
            'target_device': Device(id='d2', name='SW2', role=DeviceRole.AGGREGATION_SWITCH, rack='R1'),
            'source_port': Port(id='p1', name='Eth1/1', speed=10000),
            'target_port': Port(id='p2', name='Eth1/1', speed=10000),
            'distance': 5,
            'source_speed': 10000,
            'target_speed': 10000,
        }
    
    @pytest.mark.asyncio
    async def test_same_rack_scoring(self, scoring_engine, sample_candidate, sample_context):
        """测试同机柜评分"""
        score, details = await scoring_engine._score_same_rack(sample_candidate, sample_context)
        assert score == 30
        assert details == "Same rack: R1"
    
    @pytest.mark.asyncio
    async def test_dac_scoring_short_distance(self, scoring_engine, sample_candidate, sample_context):
        """测试短距离DAC评分"""
        score, details = await scoring_engine._score_dac(sample_candidate, sample_context)
        assert score == 20
        assert "DAC suitable" in details
    
    @pytest.mark.asyncio
    async def test_speed_match_scoring(self, scoring_engine, sample_candidate, sample_context):
        """测试速率匹配评分"""
        score, details = await scoring_engine._score_speed_match(sample_candidate, sample_context)
        assert score == 10
        assert "Exact speed match" in details
    
    @pytest.mark.asyncio
    async def test_score_candidate(self, scoring_engine, sample_candidate, sample_context):
        """测试候选评分"""
        result = await scoring_engine.score_candidate(sample_candidate, sample_context)
        assert result.total_score > 0
        assert len(result.breakdown) > 0
        assert result.candidate_id == sample_candidate.id

# tests/unit/engine/test_optimization_engine.py
class TestOptimizationEngine:
    """优化引擎测试"""
    
    @pytest.fixture
    def optimization_engine(self):
        return OptimizationEngine()
    
    @pytest.fixture
    def sample_candidates(self):
        return [
            Candidate(id=f"c-{i}", 
                     source_device_id=f"d{i}",
                     target_device_id=f"d{i+1}",
                     parameters={'speed': 10000, 'distance': i*10})
            for i in range(5)
        ]
    
    @pytest.fixture
    def sample_score_results(self, sample_candidates):
        return [
            ScoreResult(candidate_id=c.id, total_score=100 - i*10, breakdown=[])
            for i, c in enumerate(sample_candidates)
        ]
    
    @pytest.mark.asyncio
    async def test_optimize_selection(self, optimization_engine, 
                                      sample_candidates, sample_score_results):
        """测试优化选择"""
        result = await optimization_engine.optimize(
            sample_candidates, 
            sample_score_results,
            {'required_connections': 3}
        )
        assert len(result.selected_candidates) >= 3
        assert result.constraints_satisfied is True
        assert result.total_score > 0
```

## 3. 集成测试

python

```
# tests/integration/test_engine_flow.py
import pytest
from src.engine.rule import RuleEngine
from src.engine.candidate import CandidateEngine
from src.engine.constraint import ConstraintEngine
from src.engine.scoring import ScoringEngine
from src.engine.optimization import OptimizationEngine
from src.engine.generator import ConnectionGenerator

class TestEngineFlow:
    """引擎流程集成测试"""
    
    @pytest.fixture
    def test_devices(self):
        return [
            Device(id='core-1', name='Core-SW-1', role=DeviceRole.CORE_SWITCH),
            Device(id='core-2', name='Core-SW-2', role=DeviceRole.CORE_SWITCH),
            Device(id='agg-1', name='Agg-SW-1', role=DeviceRole.AGGREGATION_SWITCH),
            Device(id='agg-2', name='Agg-SW-2', role=DeviceRole.AGGREGATION_SWITCH),
        ]
    
    @pytest.fixture
    def test_ports(self, test_devices):
        ports = []
        for device in test_devices:
            for i in range(4):
                ports.append(
                    Port(id=f"{device.id}-p{i}", 
                         name=f"Eth{i+1}/1",
                         device_id=device.id,
                         speed=10000,
                         status=PortStatus.AVAILABLE)
                )
        return ports
    
    @pytest.fixture
    def rule_repository(self):
        # 创建测试规则
        return RuleRepository(Path("tests/data/rules"))
    
    @pytest.mark.asyncio
    async def test_full_flow(self, test_devices, test_ports, rule_repository):
        """测试完整流程"""
        # 1. 规则引擎
        rule_engine = RuleEngine(rule_repository)
        context = RuleContext(
            devices=test_devices,
            ports=test_ports,
            source_device=test_devices[0],
            target_device=test_devices[2]
        )
        results = await rule_engine.process(context)
        assert len(results) > 0
        
        # 2. 候选引擎
        candidate_engine = CandidateEngine()
        candidates = await candidate_engine.generate_candidates(
            [test_devices[0]], 
            [test_devices[2]],
            {'min_speed': 10000}
        )
        assert len(candidates) > 0
        
        # 3. 约束引擎
        constraint_engine = ConstraintEngine()
        constraints = [
            {'type': 'speed', 'speed': 10000},
            {'type': 'media', 'media': ['SMF']}
        ]
        constraint_results = await constraint_engine.check_candidates(
            candidates, constraints
        )
        passed = [r for r in constraint_results if r.passed]
        assert len(passed) > 0
        
        # 4. 评分引擎
        scoring_engine = ScoringEngine()
        score_results = await scoring_engine.score_candidates(passed, context)
        assert len(score_results) > 0
        
        # 5. 优化引擎
        optimization_engine = OptimizationEngine()
        optimized = await optimization_engine.optimize(
            passed, score_results,
            {'required_connections': 2}
        )
        assert len(optimized.selected_candidates) >= 2
        
        # 6. 连接生成器
        generator = ConnectionGenerator()
        connections = await generator.generate_connections(
            optimized.selected_candidates, context
        )
        assert len(connections) > 0
```



## 4. 场景测试

python

```
# tests/scenario/test_three_tier.py
import pytest
from src.scenario import TopologyScenarioGenerator

class TestThreeTierScenario:
    """三层架构场景测试"""
    
    @pytest.fixture
    def scenario_generator(self):
        return TopologyScenarioGenerator()
    
    @pytest.mark.asyncio
    async def test_generate_three_tier(self, scenario_generator):
        """测试生成三层架构"""
        scenario = await scenario_generator.generate_three_tier(
            core_count=2,
            agg_count=4,
            access_count=8
        )
        
        assert scenario.type == "three_tier"
        assert len(scenario.devices) == 2 + 4 + 8 + 32  # 加上服务器
        assert scenario.parameters['core_count'] == 2
        assert scenario.parameters['agg_count'] == 4
        assert scenario.parameters['access_count'] == 8
    
    @pytest.mark.asyncio
    async def test_three_tier_connections(self, scenario_generator):
        """测试三层架构连接"""
        scenario = await scenario_generator.generate_three_tier()
        
        # 验证连接数量
        core_count = scenario.parameters['core_count']
        agg_count = scenario.parameters['agg_count']
        
        expected_core_agg_links = core_count * agg_count
        # 实际实现需要生成连接并验证
```