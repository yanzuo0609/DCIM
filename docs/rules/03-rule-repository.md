# Rule Repository - 规则库实现

## 1. 规则库架构

rules/
├── topology/
│ ├── core-aggregation.yaml
│ ├── aggregation-access.yaml
│ ├── access-server.yaml
│ ├── spine-leaf.yaml
│ ├── leaf-server.yaml
│ ├── router-firewall.yaml
│ ├── firewall-lb.yaml
│ └── server-storage.yaml
├── redundancy/
│ ├── single-uplink.yaml
│ ├── dual-uplink.yaml
│ ├── multi-uplink.yaml
│ ├── device-diversity.yaml
│ ├── rack-diversity.yaml
│ └── path-diversity.yaml
├── mlag/
│ ├── peer-link.yaml
│ ├── keepalive.yaml
│ └── downstream.yaml
├── media/
│ ├── dac.yaml
│ ├── aoc.yaml
│ ├── smf.yaml
│ ├── mmf.yaml
│ └── copper.yaml
├── module/
│ ├── sfp.yaml
│ ├── sfp28.yaml
│ ├── qsfp.yaml
│ ├── qsfp28.yaml
│ └── qsfp-dd.yaml
├── cable/
│ ├── patch-cable.yaml
│ ├── trunk-cable.yaml
│ └── breakout-cable.yaml
├── patch/
│ ├── patch-panel-rules.yaml
│ └── odf-rules.yaml
├── storage/
│ ├── san-connectivity.yaml
│ └── storage-tiering.yaml
├── security/
│ ├── firewall-placement.yaml
│ └── zone-separation.yaml
├── allocation/
│ ├── port-allocation.yaml
│ └── module-allocation.yaml
└── validation/
├── speed-consistency.yaml
└── media-consistency.yaml

text

```
## 2. 规则加载器

​```python
from typing import List, Optional, Dict, Any, Set
from pathlib import Path
import yaml
import logging
from datetime import datetime
import asyncio
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)

class RuleRepository:
    """规则仓库"""
    
    def __init__(self, rules_dir: Path, parser: Optional[DSLParser] = None):
        self.rules_dir = rules_dir
        self.parser = parser or DSLParser()
        self.rules: Dict[str, Rule] = {}
        self.rules_by_type: Dict[str, List[Rule]] = {}
        self.rules_by_tag: Dict[str, List[Rule]] = {}
        self._lock = asyncio.Lock()
        self._loaded = False
    
    async def load(self) -> None:
        """加载所有规则"""
        async with self._lock:
            if self._loaded:
                return
            
            # 使用线程池执行文件IO
            with ThreadPoolExecutor() as executor:
                loop = asyncio.get_event_loop()
                rules = await loop.run_in_executor(
                    executor, self._load_from_directory
                )
            
            self._index_rules(rules)
            self._loaded = True
            logger.info(f"Loaded {len(rules)} rules from {self.rules_dir}")
    
    def _load_from_directory(self) -> List[Rule]:
        """从目录加载规则（同步）"""
        rules = []
        for yaml_file in self.rules_dir.glob("**/*.yaml"):
            try:
                rule = self.parser.parse_file(yaml_file)
                rules.append(rule)
            except Exception as e:
                logger.error(f"Failed to load {yaml_file}: {e}")
        return rules
    
    def _index_rules(self, rules: List[Rule]) -> None:
        """索引规则"""
        self.rules = {}
        self.rules_by_type = {}
        self.rules_by_tag = {}
        
        for rule in rules:
            # 按ID索引
            self.rules[rule.id] = rule
            
            # 按类型索引
            if rule.type not in self.rules_by_type:
                self.rules_by_type[rule.type] = []
            self.rules_by_type[rule.type].append(rule)
            
            # 按标签索引
            for tag in rule.tags:
                if tag not in self.rules_by_tag:
                    self.rules_by_tag[tag] = []
                self.rules_by_tag[tag].append(rule)
    
    async def get(self, rule_id: str) -> Optional[Rule]:
        """获取规则"""
        await self.ensure_loaded()
        return self.rules.get(rule_id)
    
    async def get_by_type(self, rule_type: str) -> List[Rule]:
        """按类型获取规则"""
        await self.ensure_loaded()
        return self.rules_by_type.get(rule_type, [])
    
    async def get_by_tag(self, tag: str) -> List[Rule]:
        """按标签获取规则"""
        await self.ensure_loaded()
        return self.rules_by_tag.get(tag, [])
    
    async def find(self, criteria: Dict[str, Any]) -> List[Rule]:
        """按条件查找规则"""
        await self.ensure_loaded()
        results = []
        for rule in self.rules.values():
            if self._matches_criteria(rule, criteria):
                results.append(rule)
        return sorted(results, key=lambda r: r.priority, reverse=True)
    
    def _matches_criteria(self, rule: Rule, criteria: Dict[str, Any]) -> bool:
        """检查规则是否匹配条件"""
        for key, value in criteria.items():
            if key == 'type':
                if rule.type != value:
                    return False
            elif key == 'tag':
                if value not in rule.tags:
                    return False
            elif key == 'enabled':
                if rule.enabled != value:
                    return False
            elif hasattr(rule, key):
                if getattr(rule, key) != value:
                    return False
        return True
    
    async def reload(self) -> None:
        """重新加载规则"""
        self._loaded = False
        await self.load()
    
    async def ensure_loaded(self) -> None:
        """确保规则已加载"""
        if not self._loaded:
            await self.load()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取规则库统计信息"""
        return {
            "total_rules": len(self.rules),
            "by_type": {k: len(v) for k, v in self.rules_by_type.items()},
            "by_tag": {k: len(v) for k, v in self.rules_by_tag.items()},
            "loaded": self._loaded,
            "rules_dir": str(self.rules_dir)
        }
```



## 3. 规则缓存

python

```
from functools import lru_cache
from typing import Optional
import hashlib
import json
import time

class RuleCache:
    """规则缓存"""
    
    def __init__(self, max_size: int = 1000, ttl: int = 300):
        self.max_size = max_size
        self.ttl = ttl  # 秒
        self._cache = {}
        self._timestamps = {}
    
    def get(self, key: str) -> Optional[Any]:
        """获取缓存"""
        if key in self._cache:
            if time.time() - self._timestamps[key] < self.ttl:
                return self._cache[key]
            else:
                # 过期，删除
                del self._cache[key]
                del self._timestamps[key]
        return None
    
    def set(self, key: str, value: Any) -> None:
        """设置缓存"""
        if len(self._cache) >= self.max_size:
            # LRU淘汰
            oldest = min(self._timestamps, key=self._timestamps.get)
            del self._cache[oldest]
            del self._timestamps[oldest]
        
        self._cache[key] = value
        self._timestamps[key] = time.time()
    
    def clear(self) -> None:
        """清空缓存"""
        self._cache.clear()
        self._timestamps.clear()
    
    def get_key(self, rule_id: str, context: Dict[str, Any]) -> str:
        """生成缓存键"""
        content = f"{rule_id}:{json.dumps(context, sort_keys=True)}"
        return hashlib.md5(content.encode()).hexdigest()
```



## 4. 规则验证器

python

```
from typing import List, Tuple, Optional
import re

class RuleValidator:
    """规则验证器"""
    
    def __init__(self):
        self.errors: List[str] = []
        self.warnings: List[str] = []
    
    def validate(self, rule: Rule) -> Tuple[bool, List[str], List[str]]:
        """验证规则"""
        self.errors = []
        self.warnings = []
        
        # 验证基本字段
        self._validate_basic(rule)
        
        # 验证条件
        self._validate_conditions(rule.when)
        
        # 验证动作
        self._validate_actions(rule.then)
        
        # 验证评分
        if rule.scoring:
            self._validate_scoring(rule.scoring)
        
        return len(self.errors) == 0, self.errors, self.warnings
    
    def _validate_basic(self, rule: Rule) -> None:
        """验证基本字段"""
        if not rule.id:
            self.errors.append("Rule ID is required")
        if not re.match(r'^[a-z][a-z0-9-]*$', rule.id):
            self.errors.append(f"Invalid rule ID format: {rule.id}")
        
        if not rule.name:
            self.warnings.append("Rule name is empty")
        
        if not rule.type:
            self.errors.append("Rule type is required")
        
        if rule.priority < 0:
            self.warnings.append(f"Negative priority: {rule.priority}")
    
    def _validate_conditions(self, conditions: Dict[str, Any]) -> None:
        """验证条件"""
        if not conditions:
            self.warnings.append("Rule has no conditions")
        
        for key, value in conditions.items():
            if key in ['and', 'or']:
                if not isinstance(value, list):
                    self.errors.append(f"Condition '{key}' must be a list")
                else:
                    for cond in value:
                        self._validate_conditions(cond)
            elif key == 'not':
                if not isinstance(value, dict):
                    self.errors.append("'not' condition must be a dict")
                else:
                    self._validate_conditions(value)
    
    def _validate_actions(self, actions: Dict[str, Any]) -> None:
        """验证动作"""
        if not actions.get('connection'):
            self.errors.append("Missing 'connection' in actions")
        else:
            connection = actions['connection']
            if not connection.get('link_type'):
                self.warnings.append("No link_type specified in connection")
    
    def _validate_scoring(self, scoring: ScoringConfig) -> None:
        """验证评分"""
        for field, value in scoring.dict().items():
            if isinstance(value, int):
                if value < 0:
                    self.errors.append(f"Negative score for {field}: {value}")
                elif value > 100:
                    self.warnings.append(f"Score > 100 for {field}: {value}")
```



## 5. 规则热加载

python

```
import watchdog.observers
import watchdog.events
from pathlib import Path

class RuleHotLoader:
    """规则热加载器"""
    
    def __init__(self, repository: RuleRepository, reload_interval: int = 60):
        self.repository = repository
        self.reload_interval = reload_interval
        self._running = False
        self._task = None
        self._last_reload = 0
    
    async def start(self) -> None:
        """启动热加载"""
        self._running = True
        self._task = asyncio.create_task(self._reload_loop())
        logger.info("Rule hot loader started")
    
    async def stop(self) -> None:
        """停止热加载"""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("Rule hot loader stopped")
    
    async def _reload_loop(self) -> None:
        """重载循环"""
        while self._running:
            try:
                # 检查文件修改时间
                modified = self._check_modifications()
                if modified:
                    await self.repository.reload()
                    self._last_reload = time.time()
                    logger.info("Rules reloaded due to modifications")
            except Exception as e:
                logger.error(f"Error in reload loop: {e}")
            
            await asyncio.sleep(self.reload_interval)
    
    def _check_modifications(self) -> bool:
        """检查文件是否被修改"""
        # 简单实现：检查mtime
        # 实际可以使用watchdog
        return False
    
    def start_watchdog(self) -> None:
        """使用watchdog监控文件变化"""
        class RuleFileHandler(watchdog.events.FileSystemEventHandler):
            def __init__(self, loader):
                self.loader = loader
            
            def on_modified(self, event):
                if event.src_path.endswith('.yaml'):
                    asyncio.create_task(self.loader.repository.reload())
        
        observer = watchdog.observers.Observer()
        handler = RuleFileHandler(self)
        observer.schedule(handler, str(self.repository.rules_dir), recursive=True)
        observer.start()
```



## 6. 规则优先级管理

python

```
class RulePriorityManager:
    """规则优先级管理器"""
    
    def __init__(self):
        self.priority_groups: Dict[int, List[str]] = {}
    
    def set_priority(self, rule_id: str, priority: int) -> None:
        """设置规则优先级"""
        # 从旧组移除
        for group, rules in self.priority_groups.items():
            if rule_id in rules:
                rules.remove(rule_id)
                break
        
        # 添加到新组
        if priority not in self.priority_groups:
            self.priority_groups[priority] = []
        self.priority_groups[priority].append(rule_id)
    
    def get_ordered_rules(self, rules: List[Rule]) -> List[Rule]:
        """按优先级排序规则"""
        return sorted(rules, key=lambda r: r.priority, reverse=True)
    
    def resolve_conflict(self, rules: List[Rule]) -> Rule:
        """解决规则冲突"""
        # 先按优先级排序
        sorted_rules = self.get_ordered_rules(rules)
        
        # 如果有明确冲突解决策略
        for rule in sorted_rules:
            if rule.conflict_resolution:
                if rule.conflict_resolution == "override":
                    return rule
        
        # 默认返回优先级最高的
        return sorted_rules[0]
```