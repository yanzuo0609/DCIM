# Media Module Cable - 介质、模块、线缆管理

## 1. 介质类型

| 介质 | 说明 | 适用距离 |
|------|------|----------|
| Copper | 铜缆 | < 100m |
| SMF | 单模光纤 | 2km - 40km |
| MMF | 多模光纤 | < 300m |
| DAC | 直连铜缆 | < 7m |
| AOC | 有源光缆 | < 100m |

## 2. 模块类型

| 模块 | 速率 | 传输距离 | 应用 |
|------|------|----------|------|
| SFP | 1G | < 80km | 千兆以太网 |
| SFP+ | 10G | < 80km | 万兆以太网 |
| SFP28 | 25G | < 80km | 25G以太网 |
| QSFP+ | 40G | < 40km | 40G以太网 |
| QSFP28 | 100G | < 40km | 100G以太网 |
| QSFP-DD | 400G | < 10km | 400G以太网 |

## 3. 线缆管理

```python
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import uuid
import logging

logger = logging.getLogger(__name__)

class CableType(str, Enum):
    DAC = "dac"
    AOC = "aoc"
    SMF = "smf"
    MMF = "mmf"
    CAT6 = "cat6"
    CAT6A = "cat6a"
    CAT7 = "cat7"
    CAT8 = "cat8"
    MPO_SMF = "mpo_smf"
    MPO_MMF = "mpo_mmf"

class ModuleFormFactor(str, Enum):
    SFP = "sfp"
    SFP_PLUS = "sfp_plus"
    SFP28 = "sfp28"
    QSFP = "qsfp"
    QSFP_PLUS = "qsfp_plus"
    QSFP28 = "qsfp28"
    QSFP_DD = "qsfp_dd"
    OSFP = "osfp"
    CFP = "cfp"
    CFP2 = "cfp2"

@dataclass
class MediaSpec:
    """介质规格"""
    type: str
    max_distance: float
    speed: int
    fiber_count: Optional[int] = None
    wavelength: Optional[int] = None

@dataclass
class ModuleSpec:
    """模块规格"""
    form_factor: ModuleFormFactor
    speed: int
    media_type: str
    max_distance: float
    connector: str
    part_number: str
    vendor: Optional[str] = None

@dataclass
class CableSpec:
    """线缆规格"""
    type: CableType
    length: float
    speed: int
    connector_a: str
    connector_b: str
    media_type: str
    part_number: str
    vendor: Optional[str] = None

class MediaManager:
    """介质管理器"""
    
    def __init__(self):
        self._media_catalog: Dict[str, MediaSpec] = {}
        self._module_catalog: Dict[str, ModuleSpec] = {}
        self._cable_catalog: Dict[str, CableSpec] = {}
        
        self._load_default_catalog()
    
    def _load_default_catalog(self) -> None:
        """加载默认目录"""
        # 介质
        self._media_catalog = {
            'smf': MediaSpec('smf', 10000, 100000),
            'mmf': MediaSpec('mmf', 300, 10000),
            'copper': MediaSpec('copper', 100, 1000),
            'dac': MediaSpec('dac', 7, 10000),
        }
        
        # 模块
        self._module_catalog = {
            'sfp-1g': ModuleSpec(ModuleFormFactor.SFP, 1000, 'copper', 100, 'RJ45', 'SFP-1G'),
            'sfp-1g-smf': ModuleSpec(ModuleFormFactor.SFP, 1000, 'smf', 80000, 'LC', 'SFP-1G-SMF'),
            'sfp-10g': ModuleSpec(ModuleFormFactor.SFP_PLUS, 10000, 'copper', 30, 'RJ45', 'SFP-10G'),
            'sfp-10g-smf': ModuleSpec(ModuleFormFactor.SFP_PLUS, 10000, 'smf', 80000, 'LC', 'SFP-10G-SMF'),
            'sfp-10g-mmf': ModuleSpec(ModuleFormFactor.SFP_PLUS, 10000, 'mmf', 300, 'LC', 'SFP-10G-MMF'),
            'sfp28-25g': ModuleSpec(ModuleFormFactor.SFP28, 25000, 'smf', 80000, 'LC', 'SFP28-25G'),
            'qsfp-40g': ModuleSpec(ModuleFormFactor.QSFP_PLUS, 40000, 'smf', 40000, 'MPO', 'QSFP-40G'),
            'qsfp-40g-mmf': ModuleSpec(ModuleFormFactor.QSFP_PLUS, 40000, 'mmf', 100, 'MPO', 'QSFP-40G-MMF'),
            'qsfp28-100g': ModuleSpec(ModuleFormFactor.QSFP28, 100000, 'smf', 40000, 'MPO', 'QSFP28-100G'),
            'qsfp-dd-400g': ModuleSpec(ModuleFormFactor.QSFP_DD, 400000, 'smf', 10000, 'MPO', 'QSFP-DD-400G'),
        }
        
        # 线缆
        self._cable_catalog = {
            'dac-1m': CableSpec(CableType.DAC, 1, 10000, 'SFP', 'SFP', 'copper', 'DAC-1M'),
            'dac-3m': CableSpec(CableType.DAC, 3, 10000, 'SFP', 'SFP', 'copper', 'DAC-3M'),
            'dac-5m': CableSpec(CableType.DAC, 5, 10000, 'SFP', 'SFP', 'copper', 'DAC-5M'),
            'aoc-10m': CableSpec(CableType.AOC, 10, 10000, 'SFP', 'SFP', 'aoc', 'AOC-10M'),
            'smf-10m': CableSpec(CableType.SMF, 10, 100000, 'LC', 'LC', 'smf', 'SMF-10M'),
            'smf-100m': CableSpec(CableType.SMF, 100, 100000, 'LC', 'LC', 'smf', 'SMF-100M'),
            'mmf-10m': CableSpec(CableType.MMF, 10, 10000, 'LC', 'LC', 'mmf', 'MMF-10M'),
            'cat6-10m': CableSpec(CableType.CAT6, 10, 1000, 'RJ45', 'RJ45', 'copper', 'CAT6-10M'),
        }
    
    def get_module(self, part_number: str) -> Optional[ModuleSpec]:
        """获取模块规格"""
        return self._module_catalog.get(part_number)
    
    def get_module_for_speed(self, speed: int, distance: float) -> Optional[ModuleSpec]:
        """根据速率和距离选择模块"""
        for module in self._module_catalog.values():
            if module.speed == speed and module.max_distance >= distance:
                return module
        return None
    
    def get_cable(self, part_number: str) -> Optional[CableSpec]:
        """获取线缆规格"""
        return self._cable_catalog.get(part_number)
    
    def get_cable_for_connection(self, speed: int, distance: float) -> Optional[CableSpec]:
        """根据速率和距离选择线缆"""
        candidates = []
        
        for cable in self._cable_catalog.values():
            if cable.speed >= speed and cable.length >= distance:
                candidates.append(cable)
        
        if not candidates:
            return None
        
        # 选择最短的线缆
        return min(candidates, key=lambda c: c.length)
    
    def get_media_type(self, media_type: str) -> Optional[MediaSpec]:
        """获取介质规格"""
        return self._media_catalog.get(media_type)
    
    def is_compatible(self, module1: ModuleSpec, module2: ModuleSpec) -> bool:
        """检查两个模块是否兼容"""
        if module1.speed != module2.speed:
            return False
        
        if module1.media_type != module2.media_type:
            return False
        
        if module1.connector != module2.connector:
            return False
        
        return True
    
    def is_cable_compatible(self, cable: CableSpec, 
                           module_a: ModuleSpec, 
                           module_b: ModuleSpec) -> bool:
        """检查线缆与模块是否兼容"""
        # 检查速率
        if cable.speed < module_a.speed or cable.speed < module_b.speed:
            return False
        
        # 检查连接器
        if cable.connector_a != module_a.connector:
            return False
        
        if cable.connector_b != module_b.connector:
            return False
        
        # 检查介质
        if cable.media_type != module_a.media_type:
            return False
        
        if cable.media_type != module_b.media_type:
            return False
        
        return True

class CableSelector:
    """线缆选择器"""
    
    def __init__(self, media_manager: MediaManager):
        self.media_manager = media_manager
    
    def select_cable(self, source_port: Port, target_port: Port,
                    distance: float) -> Optional[Tuple[CableSpec, ModuleSpec, ModuleSpec]]:
        """选择线缆和模块"""
        # 确定速率
        speed = min(source_port.speed, target_port.speed)
        
        # 选择介质
        media_type = self._determine_media(source_port, target_port, distance)
        if not media_type:
            return None
        
        # 选择模块
        source_module = self.media_manager.get_module_for_speed(speed, distance)
        target_module = self.media_manager.get_module_for_speed(speed, distance)
        
        if not source_module or not target_module:
            return None
        
        # 选择线缆
        cable = self.media_manager.get_cable_for_connection(speed, distance)
        if not cable:
            return None
        
        return cable, source_module, target_module
    
    def _determine_media(self, source_port: Port, target_port: Port,
                        distance: float) -> Optional[str]:
        """确定介质类型"""
        if distance <= 7:
            return 'dac'
        elif distance <= 30 and source_port.speed <= 1000:
            return 'copper'
        elif distance <= 300:
            return 'mmf'
        elif distance <= 80000:
            return 'smf'
        else:
            return None
```