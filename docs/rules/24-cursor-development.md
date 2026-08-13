# Cursor Development - Cursor开发执行规范

## 1. 开发阶段

| 阶段 | 内容 | 输出 | 测试 |
|------|------|------|------|
| Phase 1 | Domain Model | 领域模型类 | 单元测试 |
| Phase 2 | DSL Parser | DSL解析器 | 单元测试 |
| Phase 3 | Rule Repository | 规则仓库 | 单元测试 |
| Phase 4 | Rule Engine | 规则引擎 | 单元测试 |
| Phase 5 | Candidate Engine | 候选引擎 | 单元测试 |
| Phase 6 | Constraint Engine | 约束引擎 | 单元测试 |
| Phase 7 | Scoring Engine | 评分引擎 | 单元测试 |
| Phase 8 | Optimization Engine | 优化引擎 | 单元测试 |
| Phase 9 | Resource Allocation | 资源分配 | 单元测试 |
| Phase 10 | Connection Generator | 连接生成器 | 集成测试 |
| Phase 11 | Validation | 验证引擎 | 集成测试 |
| Phase 12 | Explain | 解释引擎 | 集成测试 |
| Phase 13 | API | API层 | API测试 |
| Phase 14 | Integration | 系统集成 | 端到端测试 |

## 2. 代码规范

### 2.1 Python代码规范

```python
# 使用类型提示
from typing import List, Optional, Dict, Any
from dataclasses import dataclass

@dataclass
class Example:
    """类文档字符串"""
    id: str
    name: str
    metadata: Optional[Dict[str, Any]] = None
    
    def method(self, param: str) -> bool:
        """方法文档字符串
        
        Args:
            param: 参数说明
            
        Returns:
            bool: 返回值说明
        """
        return True
```

### 2.2 测试规范

python

```
# tests/unit/test_example.py
import pytest

class TestExample:
    """测试类文档"""
    
    @pytest.fixture
    def setup(self):
        """测试夹具"""
        return Example(id="1", name="test")
    
    def test_method(self, setup):
        """测试方法"""
        assert setup.method("test") is True
```



### 2.3 Git提交规范

text

```
feat: 新功能
fix: 修复bug
docs: 文档更新
style: 代码风格
refactor: 重构
perf: 性能优化
test: 测试相关
chore: 构建/工具
```



## 3. 开发流程

### 3.1 每个Phase的开发步骤

1. **设计**：阅读相关文档，理解需求
2. **实现**：编写代码
3. **测试**：编写单元测试
4. **验证**：运行测试确认通过
5. **审查**：代码审查
6. **合并**：合并到主分支

### 3.2 Cursor提示词模板

text

```
# Phase {X}: {Module Name}

## 任务
实现 {Module Name} 模块

## 参考文档
- docs/connection-rule-engine/{X}-{module}.md

## 要求
1. 实现所有接口
2. 使用类型提示
3. 编写单元测试
4. 覆盖率 > 90%

## 文件结构
src/{module}/
├── __init__.py
├── {module}.py
└── exceptions.py

tests/unit/{module}/
├── __init__.py
└── test_{module}.py

## 开始实现
```



### 3.3 代码审查检查清单

- □ 

  代码符合规范

- □ 

  类型提示完整

- □ 

  文档字符串完整

- □ 

  单元测试通过

- □ 

  测试覆盖率达标

- □ 

  无重复代码

- □ 

  异常处理完善

- □ 

  日志记录完善

## 4. 里程碑

| 里程碑 | 目标                            | 日期   |
| :----- | :------------------------------ | :----- |
| M1     | Domain Model + DSL Parser       | Week 1 |
| M2     | Rule Repository + Rule Engine   | Week 2 |
| M3     | Candidate + Constraint Engine   | Week 3 |
| M4     | Scoring + Optimization Engine   | Week 4 |
| M5     | Resource Allocation + Generator | Week 5 |
| M6     | Validation + Explain Engine     | Week 6 |
| M7     | API + Integration               | Week 7 |
| M8     | Testing + Documentation         | Week 8 |

## 5. 环境配置

### 5.1 开发环境

bash

```
# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

# 安装依赖
pip install -r requirements.txt
pip install -r requirements-dev.txt

# 运行测试
pytest tests/ -v --cov=src

# 代码格式化
black src/ tests/
isort src/ tests/

# 类型检查
mypy src/
```



### 5.2 requirements.txt

text

```
pydantic>=2.0.0
pyyaml>=6.0.0
networkx>=3.0.0
fastapi>=0.100.0
uvicorn>=0.23.0
numpy>=1.24.0
scipy>=1.10.0
```



### 5.3 requirements-dev.txt

text

```
pytest>=7.0.0
pytest-cov>=4.0.0
pytest-asyncio>=0.21.0
black>=23.0.0
isort>=5.12.0
mypy>=1.0.0
pre-commit>=3.0.0
```



## 6. 注意事项

1. **严格模块分离**：每个模块只负责自己的职责
2. **禁止循环依赖**：使用依赖注入
3. **异步优先**：使用async/await
4. **类型安全**：使用类型提示
5. **测试驱动**：先写测试再写代码
6. **文档同步**：代码和文档一起更新

