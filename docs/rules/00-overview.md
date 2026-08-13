# Connection Rule Engine - 系统总体架构

## 1. 项目愿景

构建一个智能的网络连接决策引擎，能够根据网络拓扑、设备能力、资源状态和业务需求，自动生成最优的物理连接方案和逻辑链路。

## 2. 核心能力

- **规则驱动**：基于YAML DSL定义的可扩展规则体系
- **智能决策**：候选生成 + 约束检查 + 评分优化
- **物理感知**：完整的光模块、线缆、配线架、ODF路径建模
- **冗余设计**：设备、端口、路径、机柜多维度冗余
- **可解释性**：每个连接决策都有明确的规则依据和评分

## 3. 系统架构

┌─────────────────────────────────────────────────────────────────┐
│ Input Layer │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│ │ UI/API │ │ AI Parser │ │ Import (Excel/XML) │ │
│ └─────────────┘ └─────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ Decision Pipeline │
│ │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Phase 1: Requirement Parsing │ │
│ │ └── Scenario Resolver → Rule Selector │ │
│ └────────────────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Phase 2: Candidate Generation │ │
│ │ └── Source/Destination Matching → Candidate List │ │
│ └────────────────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Phase 3: Constraint Filtering │ │
│ │ ├── Hard Constraints (REJECT if fail) │ │
│ │ └── Soft Constraints (Penalty if fail) │ │
│ └────────────────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Phase 4: Scoring & Optimization │ │
│ │ ├── Individual Score │ │
│ │ └── Global Optimization (Resource Balancing) │ │
│ └────────────────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Phase 5: Resource Allocation │ │
│ │ ├── Port Allocation │ │
│ │ ├── Module Allocation │ │
│ │ └── Cable / Path Allocation │ │
│ └────────────────────────────────────────────────────────┘ │
│ │ │
│ ▼ │
│ ┌────────────────────────────────────────────────────────┐ │
│ │ Phase 6: Connection Generation & Validation │ │
│ │ ├── Physical Connection │ │
│ │ ├── Logical Link │ │
│ │ └── Final Validation │ │
│ └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
│
▼
┌─────────────────────────────────────────────────────────────────┐
│ Output Layer │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│ │ Connection │ │ Cable List │ │ Port Allocation │ │
│ │ Table │ │ Module List│ │ Patch/ODF Table │ │
│ └─────────────┘ └─────────────┘ └─────────────────────┘ │
│ ┌─────────────┐ ┌─────────────┐ ┌─────────────────────┐ │
│ │ Topology │ │ Rack Plan │ │ Explanation │ │
│ │ Diagram │ │ │ │ Report │ │
│ └─────────────┘ └─────────────┘ └─────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘

## 4. 技术栈建议

| 组件     | 技术选型            | 说明                 |
| -------- | ------------------- | -------------------- |
| 语言     | Python 3.11+        | 类型提示、异步支持   |
| 规则解析 | PyYAML + Pydantic   | DSL解析和验证        |
| 优化引擎 | OR-Tools / PuLP     | 全局优化求解         |
| 图处理   | NetworkX            | 拓扑图建模和路径计算 |
| API      | FastAPI             | RESTful API          |
| 测试     | pytest + pytest-cov | 单元测试和覆盖率     |
| 日志     | structlog           | 结构化日志           |
| 配置     | python-dotenv       | 环境变量管理         |

## 5. 模块依赖关系

01-domain-model → 所有模块
02-rule-dsl → 03, 04
03-rule-repository → 04
04-rule-engine → 05
05-candidate-engine → 06, 07
06-constraint-engine→ 07, 08
07-scoring-engine → 08
08-optimization-engine→ 09, 12
09-connection-generator→ 10, 11, 15, 16
10-validation-engine → 11, 18
11-explain-engine → 最终输出
12-resource-allocation→ 09, 16
13-topology-scenarios→ 01, 03
14-redundancy-model → 01, 03, 09
15-media-module-cable→ 01, 06, 09
16-patch-odf-path → 01, 09
17-device-capability→ 01, 06
18-rule-conflict → 03, 04
19-ai-requirement-parser→ 04
20-api-specification→ 所有模块
21-data-model → 持久化
22-test-specification→ 所有模块
23-example-scenarios→ 集成测试
24-cursor-development→ 开发流程

## 6. 关键设计决策

### 6.1 分离原则
- Rule ≠ Engine
- Candidate ≠ Final Connection
- Physical ≠ Logical
- Hard Constraint ≠ Soft Constraint

### 6.2 可扩展原则
- 设备类型通过配置添加，无需修改代码
- 规则通过YAML定义，无需重新编译
- 评分权重可配置
- 约束条件可插拔

### 6.3 可解释原则
- 每个决策都有规则来源
- 每个连接都有评分明细
- 支持决策路径追溯

## 7. 性能目标

| 场景 | 设备数 | 连接数  | 处理时间 |
| ---- | ------ | ------- | -------- |
| 小型 | < 1000 | < 10000 | < 1s     |
| 中型 | <2000  | < 20000 | < 5s     |
| 大型 | < 5000 | < 50000 | < 12s    |

## 8. 质量属性

- **正确性**：100%满足硬约束

- **可维护性**：模块化设计，每个模块<500行

- **可测试性**：覆盖率>90%

- **可扩展性**：新增规则类型无需修改核心引擎

  