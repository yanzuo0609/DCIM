# Validation Engine - 验证引擎

## 1. 验证内容

| 验证项 | 说明 | 严重程度 |
|--------|------|----------|
| 端口可用性 | 端口是否已被占用 | ERROR |
| 速率一致性 | 两端速率是否匹配 | ERROR |
| 介质一致性 | 两端介质是否兼容 | ERROR |
| 距离限制 | 是否超过最大传输距离 | ERROR |
| 模块兼容性 | 模块是否与设备兼容 | WARNING |
| 冗余要求 | 是否满足冗余配置 | WARNING |
| 资源冲突 | 是否存在资源冲突 | ERROR |

## 2. 验证器实现

```python
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from enum import Enum

class ValidationSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"

@dataclass
class ValidationResult:
    """验证结果"""
    passed: bool
    severity: ValidationSeverity
    message: str
    connection_id: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)

class ValidationEngine:
    """验证引擎"""
    
    def __init__(self):
        self._validators = [
            self._validate_port_availability,
            self._validate_speed_consistency,
            self._validate_media_consistency,
            self._validate_distance,
            self._validate_module_compatibility,
            self._validate_redundancy,
            self._validate_resource_conflicts,
        ]
    
    async def validate_connection(self, connection: Connection,
                                 context: Dict[str, Any]) -> List[ValidationResult]:
        """验证单个连接"""
        results = []
        
        for validator in self._validators:
            result = await validator(connection, context)
            if result:
                results.append(result)
        
        return results
    
    async def validate_connections(self, connections: List[Connection],
                                  context: Dict[str, Any]) -> Dict[str, List[ValidationResult]]:
        """验证多个连接"""
        all_results = {}
        
        for connection in connections:
            results = await self.validate_connection(connection, context)
            all_results[connection.id] = results
        
        return all_results
    
    async def _validate_port_availability(self, connection: Connection,
                                         context: Dict[str, Any]) -> Optional[ValidationResult]:
        """验证端口可用性"""
        # 检查源端口
        if connection.source.port_id:
            port = await self._get_port(connection.source.port_id, context)
            if port and port.status != PortStatus.AVAILABLE:
                return ValidationResult(
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Source port {port.name} is not available",
                    connection_id=connection.id
                )
        
        # 检查目标端口
        if connection.destination.port_id:
            port = await self._get_port(connection.destination.port_id, context)
            if port and port.status != PortStatus.AVAILABLE:
                return ValidationResult(
                    passed=False,
                    severity=ValidationSeverity.ERROR,
                    message=f"Destination port {port.name} is not available",
                    connection_id=connection.id
                )
        
        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            message="Ports are available",
            connection_id=connection.id
        )
    
    async def _validate_speed_consistency(self, connection: Connection,
                                         context: Dict[str, Any]) -> Optional[ValidationResult]:
        """验证速率一致性"""
        source_speed = context.get('source_speed', 0)
        target_speed = context.get('target_speed', 0)
        
        if source_speed != target_speed:
            return ValidationResult(
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Speed mismatch: {source_speed}Mbps vs {target_speed}Mbps",
                connection_id=connection.id,
                details={'source_speed': source_speed, 'target_speed': target_speed}
            )
        
        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            message=f"Speed consistent: {source_speed}Mbps",
            connection_id=connection.id
        )
    
    async def _validate_media_consistency(self, connection: Connection,
                                         context: Dict[str, Any]) -> Optional[ValidationResult]:
        """验证介质一致性"""
        source_media = context.get('source_media')
        target_media = context.get('target_media')
        cable_media = context.get('cable_media')
        
        if source_media and target_media and source_media != target_media:
            return ValidationResult(
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Media mismatch: {source_media} vs {target_media}",
                connection_id=connection.id,
                details={'source_media': source_media, 'target_media': target_media}
            )
        
        if cable_media and source_media and cable_media != source_media:
            return ValidationResult(
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Cable media mismatch: {cable_media} vs {source_media}",
                connection_id=connection.id
            )
        
        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            message=f"Media consistent",
            connection_id=connection.id
        )
    
    async def _validate_distance(self, connection: Connection,
                                context: Dict[str, Any]) -> Optional[ValidationResult]:
        """验证距离限制"""
        distance = context.get('distance', 0)
        max_distance = context.get('max_distance', float('inf'))
        
        if distance > max_distance:
            return ValidationResult(
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Distance {distance}m exceeds max {max_distance}m",
                connection_id=connection.id,
                details={'distance': distance, 'max_distance': max_distance}
            )
        
        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            message=f"Distance {distance}m within limit",
            connection_id=connection.id
        )
    
    async def _validate_module_compatibility(self, connection: Connection,
                                            context: Dict[str, Any]) -> Optional[ValidationResult]:
        """验证模块兼容性"""
        source_module = context.get('source_module')
        target_module = context.get('target_module')
        device = context.get('device')
        
        if source_module and device:
            if device.type not in source_module.compatible_devices:
                return ValidationResult(
                    passed=False,
                    severity=ValidationSeverity.WARNING,
                    message=f"Source module {source_module.part_number} may not be compatible with {device.type}",
                    connection_id=connection.id,
                    details={'module': source_module.part_number, 'device': device.type}
                )
        
        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            message="Module compatibility verified",
            connection_id=connection.id
        )
    
    async def _validate_redundancy(self, connection: Connection,
                                  context: Dict[str, Any]) -> Optional[ValidationResult]:
        """验证冗余要求"""
        redundancy_group = connection.redundancy_group
        if redundancy_group:
            connections_in_group = context.get('connections_in_group', [])
            count = len([c for c in connections_in_group if c.redundancy_group == redundancy_group])
            
            required_count = context.get('required_redundancy', 0)
            if count < required_count:
                return ValidationResult(
                    passed=False,
                    severity=ValidationSeverity.WARNING,
                    message=f"Redundancy group {redundancy_group} has {count} connections, need {required_count}",
                    connection_id=connection.id,
                    details={'count': count, 'required': required_count}
                )
        
        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            message="Redundancy requirements satisfied",
            connection_id=connection.id
        )
    
    async def _validate_resource_conflicts(self, connection: Connection,
                                          context: Dict[str, Any]) -> Optional[ValidationResult]:
        """验证资源冲突"""
        conflicts = []
        
        # 检查端口冲突
        existing_connections = context.get('existing_connections', [])
        for existing in existing_connections:
            if existing.id == connection.id:
                continue
            
            # 检查源端口冲突
            if existing.source.port_id == connection.source.port_id:
                conflicts.append(f"Source port {connection.source.port_id} already used")
            
            # 检查目标端口冲突
            if existing.destination.port_id == connection.destination.port_id:
                conflicts.append(f"Destination port {connection.destination.port_id} already used")
        
        if conflicts:
            return ValidationResult(
                passed=False,
                severity=ValidationSeverity.ERROR,
                message=f"Resource conflicts found: {'; '.join(conflicts)}",
                connection_id=connection.id,
                details={'conflicts': conflicts}
            )
        
        return ValidationResult(
            passed=True,
            severity=ValidationSeverity.INFO,
            message="No resource conflicts",
            connection_id=connection.id
        )
    
    async def _get_port(self, port_id: str, context: Dict[str, Any]) -> Optional[Port]:
        """获取端口信息"""
        ports = context.get('ports', [])
        for port in ports:
            if port.id == port_id:
                return port
        return None

## 3. 验证报告

​```python
class ValidationReport:
    """验证报告"""
    
    def __init__(self):
        self.results: List[ValidationResult] = []
        self.errors: List[ValidationResult] = []
        self.warnings: List[ValidationResult] = []
        self.infos: List[ValidationResult] = []
    
    def add_result(self, result: ValidationResult) -> None:
        """添加验证结果"""
        self.results.append(result)
        
        if result.severity == ValidationSeverity.ERROR:
            self.errors.append(result)
        elif result.severity == ValidationSeverity.WARNING:
            self.warnings.append(result)
        else:
            self.infos.append(result)
    
    @property
    def passed(self) -> bool:
        """是否通过验证"""
        return len(self.errors) == 0
    
    @property
    def summary(self) -> Dict[str, int]:
        """汇总统计"""
        return {
            'total': len(self.results),
            'errors': len(self.errors),
            'warnings': len(self.warnings),
            'infos': len(self.infos)
        }
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'passed': self.passed,
            'summary': self.summary,
            'errors': [r.__dict__ for r in self.errors],
            'warnings': [r.__dict__ for r in self.warnings],
            'infos': [r.__dict__ for r in self.infos]
        }
```