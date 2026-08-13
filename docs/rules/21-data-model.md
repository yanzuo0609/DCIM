# Data Model - 数据模型

## 1. 数据库模型

使用SQLAlchemy定义数据模型。

```python
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

Base = declarative_base()

class DeviceModel(Base):
    """设备模型"""
    __tablename__ = "devices"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    type = Column(String(100), nullable=False)
    role = Column(String(100), nullable=False)
    vendor = Column(String(100))
    model = Column(String(100))
    
    # 位置
    rack = Column(String(50))
    rack_unit = Column(Integer)
    site = Column(String(100))
    room = Column(String(100))
    
    # 状态
    status = Column(String(50), default="ACTIVE")
    redundancy_group = Column(String(36))
    redundancy_role = Column(String(50))
    
    # 元数据
    capabilities = Column(JSON, default={})
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    # 关系
    ports = relationship("PortModel", back_populates="device", cascade="all, delete-orphan")

class PortModel(Base):
    """端口模型"""
    __tablename__ = "ports"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    device_id = Column(String(36), ForeignKey("devices.id"), nullable=False)
    name = Column(String(50), nullable=False)
    
    # 类型
    type = Column(String(50), default="ETHERNET")
    role = Column(String(50), default="UNKNOWN")
    
    # 速率
    speed = Column(Integer, nullable=False)  # Mbps
    supported_speeds = Column(JSON, default=[])
    auto_negotiate = Column(Boolean, default=True)
    
    # 物理特性
    connector = Column(String(50))
    media = Column(String(50))
    wavelength = Column(Integer)
    fiber_count = Column(Integer)
    
    # 模块
    module_id = Column(String(36))
    module_required = Column(Boolean, default=True)
    
    # 状态
    status = Column(String(50), default="AVAILABLE")
    reserved_by = Column(String(36))
    allocated_to = Column(String(36))
    
    # Breakout
    breakout_mode = Column(String(50), default="NONE")
    breakout_ports = Column(JSON, default=[])
    parent_port_id = Column(String(36))
    
    # 位置
    panel_slot = Column(String(50))
    port_index = Column(Integer)
    
    # 元数据
    metadata = Column(JSON, default={})
    
    # 关系
    device = relationship("DeviceModel", back_populates="ports")

class ConnectionModel(Base):
    """连接模型"""
    __tablename__ = "connections"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255))
    
    # 端点
    source_device_id = Column(String(36), nullable=False)
    source_port_id = Column(String(36), nullable=False)
    target_device_id = Column(String(36), nullable=False)
    target_port_id = Column(String(36), nullable=False)
    
    source_module_id = Column(String(36))
    target_module_id = Column(String(36))
    
    # 线缆
    cable_id = Column(String(36))
    
    # 类型
    type = Column(String(50), default="PHYSICAL")
    link_type = Column(String(50), nullable=False)
    
    # 路径
    path_nodes = Column(JSON, default=[])
    total_length = Column(Float)
    hops = Column(Integer, default=0)
    
    # 冗余
    redundancy_group = Column(String(36))
    redundancy_index = Column(Integer)
    
    # 规则
    rule_id = Column(String(100))
    rule_name = Column(String(255))
    
    # 评分
    score = Column(Float)
    score_breakdown = Column(JSON, default={})
    
    # 验证
    validated = Column(Boolean, default=False)
    validation_errors = Column(JSON, default=[])
    validation_warnings = Column(JSON, default=[])
    
    # 解释
    explanation = Column(Text)
    
    # 状态
    status = Column(String(50), default="DRAFT")
    
    # 元数据
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class CableModel(Base):
    """线缆模型"""
    __tablename__ = "cables"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    part_number = Column(String(100), nullable=False)
    vendor = Column(String(100))
    
    type = Column(String(50), nullable=False)
    connector_a = Column(String(50), nullable=False)
    connector_b = Column(String(50), nullable=False)
    
    speed = Column(Integer, nullable=False)
    length_m = Column(Float, nullable=False)
    max_distance_m = Column(Float)
    fiber_count = Column(Integer)
    polarity = Column(String(10))
    media = Column(String(50), nullable=False)
    color = Column(String(50))
    
    status = Column(String(50), default="AVAILABLE")
    allocated_to = Column(String(36))
    path = Column(JSON, default=[])
    
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)

class ModuleModel(Base):
    """模块模型"""
    __tablename__ = "modules"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    part_number = Column(String(100), nullable=False)
    vendor = Column(String(100))
    
    form_factor = Column(String(50), nullable=False)
    speed = Column(Integer, nullable=False)
    media = Column(String(50), nullable=False)
    protocol = Column(String(50), default="ETHERNET")
    
    wavelength = Column(Integer)
    fiber_count = Column(Integer)
    connector = Column(String(50))
    
    max_distance_km = Column(Float, nullable=False)
    
    compatible_devices = Column(JSON, default=[])
    compatible_ports = Column(JSON, default=[])
    
    status = Column(String(50), default="AVAILABLE")
    allocated_to = Column(String(36))
    
    operating_temp_min = Column(Float)
    operating_temp_max = Column(Float)
    
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)

class RuleModel(Base):
    """规则模型"""
    __tablename__ = "rules"
    
    id = Column(String(100), primary_key=True)
    name = Column(String(255), nullable=False)
    version = Column(String(50), default="1.0.0")
    type = Column(String(50), nullable=False)
    
    priority = Column(Integer, default=0)
    enabled = Column(Boolean, default=True)
    
    when_condition = Column(JSON, nullable=False)
    then_action = Column(JSON, nullable=False)
    
    scoring = Column(JSON)
    constraints = Column(JSON, default=[])
    
    conflict_resolution = Column(String(50))
    conflict_priority = Column(Integer)
    
    description = Column(Text)
    tags = Column(JSON, default=[])
    metadata = Column(JSON, default={})
    
    effective_from = Column(DateTime)
    effective_to = Column(DateTime)
    
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

class PatchPanelModel(Base):
    """配线架模型"""
    __tablename__ = "patch_panels"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    type = Column(String(50), nullable=False)
    
    rack = Column(String(50), nullable=False)
    rack_unit = Column(Integer, nullable=False)
    
    port_count = Column(Integer, nullable=False)
    ports = Column(JSON, default=[])
    
    vendor = Column(String(100))
    model = Column(String(100))
    
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)

class ODFModel(Base):
    """ODF模型"""
    __tablename__ = "odfs"
    
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String(255), nullable=False)
    
    rack = Column(String(50), nullable=False)
    rack_unit = Column(Integer, nullable=False)
    
    ports = Column(JSON, default=[])
    fiber_count = Column(Integer, nullable=False)
    type = Column(String(50), default="STANDARD")
    
    metadata = Column(JSON, default={})
    created_at = Column(DateTime, default=datetime.now)
```