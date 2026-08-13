# AI Requirement Parser - AI需求解析器

## 1. 功能概述

AI需求解析器将自然语言需求转换为结构化的网络连接需求。

## 2. 实现代码

```python
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
import re
import json
import logging
from openai import AsyncOpenAI  # 可选

logger = logging.getLogger(__name__)

@dataclass
class ParsedRequirement:
    """解析后的需求"""
    topology_type: Optional[str] = None
    devices: List[Dict[str, Any]] = field(default_factory=list)
    connections: List[Dict[str, Any]] = field(default_factory=list)
    constraints: List[Dict[str, Any]] = field(default_factory=list)
    redundancy: Dict[str, Any] = field(default_factory=dict)
    media_preference: Optional[str] = None
    speed_requirements: Dict[str, int] = field(default_factory=dict)

class AIRequirementParser:
    """AI需求解析器"""
    
    def __init__(self, use_openai: bool = False, openai_api_key: Optional[str] = None):
        self.use_openai = use_openai
        self.openai_api_key = openai_api_key
        self._openai_client = None
        
        if use_openai and openai_api_key:
            self._openai_client = AsyncOpenAI(api_key=openai_api_key)
    
    async def parse(self, text: str) -> ParsedRequirement:
        """解析需求文本"""
        if self.use_openai:
            return await self._parse_with_openai(text)
        else:
            return self._parse_with_rules(text)
    
    def _parse_with_rules(self, text: str) -> ParsedRequirement:
        """使用规则解析"""
        parsed = ParsedRequirement()
        
        # 检测拓扑类型
        if "三层" in text or "three-tier" in text.lower():
            parsed.topology_type = "three_tier"
        elif "spine-leaf" in text.lower() or "spine leaf" in text.lower():
            parsed.topology_type = "spine_leaf"
        elif "安全" in text or "security" in text.lower():
            parsed.topology_type = "security"
        
        # 检测设备
        devices = self._extract_devices(text)
        parsed.devices = devices
        
        # 检测连接要求
        connections = self._extract_connections(text)
        parsed.connections = connections
        
        # 检测约束
        constraints = self._extract_constraints(text)
        parsed.constraints = constraints
        
        # 检测冗余要求
        if "冗余" in text or "redundant" in text.lower():
            parsed.redundancy = {
                'required': True,
                'level': self._detect_redundancy_level(text)
            }
        
        # 检测介质偏好
        if "光纤" in text or "fiber" in text.lower():
            parsed.media_preference = "fiber"
        elif "铜缆" in text or "copper" in text.lower():
            parsed.media_preference = "copper"
        
        # 检测速率要求
        speeds = self._extract_speeds(text)
        parsed.speed_requirements = speeds
        
        return parsed
    
    def _extract_devices(self, text: str) -> List[Dict[str, Any]]:
        """提取设备信息"""
        devices = []
        
        # 匹配设备模式
        patterns = [
            r'(?P<count>\d+)\s*(?:台|个)?\s*(?P<role>核心|汇聚|接入|Spine|Leaf|服务器|防火墙)',
            r'(?P<role>core|aggregation|access|spine|leaf|server|firewall)\s*(?P<count>\d+)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                role = match.group('role')
                count = int(match.group('count'))
                
                role_map = {
                    '核心': 'CORE_SWITCH',
                    '汇聚': 'AGGREGATION_SWITCH',
                    '接入': 'ACCESS_SWITCH',
                    '服务器': 'SERVER',
                    '防火墙': 'FIREWALL',
                }
                
                device_type = role_map.get(role, role.upper())
                devices.append({
                    'role': device_type,
                    'count': count,
                    'name': f"{role}-{i+1}" for i in range(count)
                })
        
        return devices
    
    def _extract_connections(self, text: str) -> List[Dict[str, Any]]:
        """提取连接要求"""
        connections = []
        
        # 匹配连接模式
        patterns = [
            r'(?P<source>核心|汇聚|接入|Spine|Leaf)\s*到\s*(?P<target>核心|汇聚|接入|Spine|Leaf)',
            r'(?P<source>core|aggregation|access|spine|leaf)\s+to\s+(?P<target>core|aggregation|access|spine|leaf)'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                source = match.group('source')
                target = match.group('target')
                
                connections.append({
                    'source_role': source.upper(),
                    'target_role': target.upper(),
                    'link_type': self._determine_link_type(source, target)
                })
        
        return connections
    
    def _extract_constraints(self, text: str) -> List[Dict[str, Any]]:
        """提取约束"""
        constraints = []
        
        # 速度约束
        speed_match = re.search(r'(?P<speed>\d+)\s*(G|g|M|m)\s*(?:bps|Bps)?', text)
        if speed_match:
            speed = int(speed_match.group('speed'))
            unit = speed_match.group('g').lower()
            if unit == 'g':
                speed *= 1000
            constraints.append({
                'type': 'speed',
                'min_speed': speed
            })
        
        # 距离约束
        distance_match = re.search(r'(?P<distance>\d+)\s*(m|km|公里|米)', text)
        if distance_match:
            distance = int(distance_match.group('distance'))
            unit = distance_match.group(2)
            if unit in ['km', '公里']:
                distance *= 1000
            constraints.append({
                'type': 'distance',
                'max_distance': distance
            })
        
        return constraints
    
    def _detect_redundancy_level(self, text: str) -> str:
        """检测冗余级别"""
        if "双" in text or "dual" in text.lower():
            return "dual"
        elif "多" in text or "multi" in text.lower():
            return "multi"
        else:
            return "single"
    
    def _extract_speeds(self, text: str) -> Dict[str, int]:
        """提取速率要求"""
        speeds = {}
        
        # 匹配各种速率格式
        patterns = [
            r'(?P<speed>\d+)\s*(?:G|g)\s*(?:bps|Bps)?',
            r'(?P<speed>\d+)\s*(?:M|m)\s*(?:bps|Bps)?'
        ]
        
        for pattern in patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE)
            for match in matches:
                speed = int(match.group('speed'))
                if 'G' in match.group(0) or 'g' in match.group(0):
                    speed *= 1000
                speeds['required'] = speed
        
        return speeds
    
    def _determine_link_type(self, source: str, target: str) -> str:
        """确定链路类型"""
        source = source.upper()
        target = target.upper()
        
        link_map = {
            ('CORE', 'AGGREGATION'): 'UPLINK',
            ('AGGREGATION', 'ACCESS'): 'DOWNLINK',
            ('ACCESS', 'SERVER'): 'ACCESS',
            ('SPINE', 'LEAF'): 'UPLINK',
        }
        
        return link_map.get((source, target), 'UNKNOWN')
    
    async def _parse_with_openai(self, text: str) -> ParsedRequirement:
        """使用OpenAI解析"""
        if not self._openai_client:
            logger.warning("OpenAI client not initialized, falling back to rule-based parsing")
            return self._parse_with_rules(text)
        
        try:
            prompt = f"""
            Parse the following network requirement text and extract structured information.
            Return as JSON with the following fields:
            - topology_type: string (three_tier, spine_leaf, security)
            - devices: array of {role, count, name}
            - connections: array of {source_role, target_role, link_type}
            - constraints: array of {type, value}
            - redundancy: {required, level}
            - media_preference: string (fiber, copper)
            - speed_requirements: object

            Text: {text}
            """
            
            response = await self._openai_client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a network requirement parser."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1
            )
            
            result = json.loads(response.choices[0].message.content)
            return ParsedRequirement(**result)
            
        except Exception as e:
            logger.error(f"OpenAI parsing failed: {e}")
            return self._parse_with_rules(text)
```