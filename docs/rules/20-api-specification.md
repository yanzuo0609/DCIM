# API Specification - API规范

## 1. API概述

Connection Rule Engine提供RESTful API，用于管理设备、规则、连接和资源。

## 2. API端点

### 2.1 设备管理

GET /api/v1/devices # 获取设备列表
POST /api/v1/devices # 创建设备
GET /api/v1/devices/{id} # 获取设备详情
PUT /api/v1/devices/{id} # 更新设备
DELETE /api/v1/devices/{id} # 删除设备
GET /api/v1/devices/{id}/ports # 获取设备端口

text

```
### 2.2 规则管理
```



GET /api/v1/rules # 获取规则列表
POST /api/v1/rules # 创建规则
GET /api/v1/rules/{id} # 获取规则详情
PUT /api/v1/rules/{id} # 更新规则
DELETE /api/v1/rules/{id} # 删除规则
POST /api/v1/rules/reload # 重新加载规则

text

```
### 2.3 连接管理
```



POST /api/v1/connections/generate # 生成连接
GET /api/v1/connections # 获取连接列表
GET /api/v1/connections/{id} # 获取连接详情
PUT /api/v1/connections/{id} # 更新连接
DELETE /api/v1/connections/{id} # 删除连接
POST /api/v1/connections/validate # 验证连接
POST /api/v1/connections/explain # 解释连接

text

```
### 2.4 资源管理
```



GET /api/v1/resources # 获取资源状态
GET /api/v1/resources/ports # 获取端口资源
GET /api/v1/resources/modules # 获取模块资源
GET /api/v1/resources/cables # 获取线缆资源
POST /api/v1/resources/allocate # 分配资源
POST /api/v1/resources/release # 释放资源

text

```
### 2.5 拓扑管理
```



GET /api/v1/topologies # 获取拓扑列表
POST /api/v1/topologies # 创建拓扑
GET /api/v1/topologies/{id} # 获取拓扑详情
POST /api/v1/topologies/generate # 生成拓扑

text

```
### 2.6 系统管理
```



GET /api/v1/health # 健康检查
GET /api/v1/metrics # 指标监控
GET /api/v1/version # 版本信息
POST /api/v1/maintenance # 维护操作

text

```
## 3. API实现

​```python
from fastapi import FastAPI, HTTPException, Depends, Query, Body
from fastapi.middleware.cors import CORSMiddleware
from typing import List, Optional, Dict, Any
from pydantic import BaseModel
import uvicorn
import logging

logger = logging.getLogger(__name__)

app = FastAPI(title="Connection Rule Engine API", version="1.0.0")

# CORS配置
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============ Models ============

class DeviceCreateRequest(BaseModel):
    name: str
    type: str
    role: str
    vendor: Optional[str] = None
    model: Optional[str] = None
    rack: Optional[str] = None
    rack_unit: Optional[int] = None
    site: Optional[str] = None

class DeviceResponse(BaseModel):
    id: str
    name: str
    type: str
    role: str
    status: str
    created_at: str

class RuleCreateRequest(BaseModel):
    id: str
    name: str
    type: str
    when: Dict[str, Any]
    then: Dict[str, Any]
    priority: int = 0
    enabled: bool = True
    description: Optional[str] = None

class RuleResponse(BaseModel):
    id: str
    name: str
    type: str
    priority: int
    enabled: bool
    version: str
    created_at: str

class GenerateConnectionRequest(BaseModel):
    scenario_id: Optional[str] = None
    source_device_ids: List[str]
    target_device_ids: List[str]
    constraints: Optional[Dict[str, Any]] = None
    count: int = 1

class ConnectionResponse(BaseModel):
    id: str
    source: Dict[str, Any]
    destination: Dict[str, Any]
    link_type: str
    status: str
    score: Optional[float] = None
    explanation: Optional[str] = None
    created_at: str

class ValidateRequest(BaseModel):
    connection_ids: List[str]

class ValidateResponse(BaseModel):
    valid: bool
    errors: List[str]
    warnings: List[str]

# ============ API Handlers ============

@app.get("/api/v1/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "version": "1.0.0"}

@app.get("/api/v1/devices")
async def list_devices(
    role: Optional[str] = None,
    rack: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """获取设备列表"""
    # 实际实现需要从设备仓库获取
    return {
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }

@app.post("/api/v1/devices")
async def create_device(request: DeviceCreateRequest):
    """创建设备"""
    # 实际实现需要调用设备服务
    return {
        "id": "device-1",
        "name": request.name,
        "type": request.type,
        "role": request.role,
        "status": "ACTIVE",
        "created_at": "2024-01-15T00:00:00Z"
    }

@app.get("/api/v1/devices/{device_id}")
async def get_device(device_id: str):
    """获取设备详情"""
    # 实际实现需要从设备仓库获取
    return {
        "id": device_id,
        "name": "Core-SW-1",
        "type": "Cisco 9500",
        "role": "CORE_SWITCH",
        "status": "ACTIVE",
        "rack": "RACK-1",
        "rack_unit": 10,
        "ports": [],
        "created_at": "2024-01-15T00:00:00Z"
    }

@app.post("/api/v1/connections/generate")
async def generate_connections(request: GenerateConnectionRequest):
    """生成连接"""
    # 实际实现需要调用连接生成器
    return {
        "connections": [],
        "stats": {
            "total": 0,
            "created": 0,
            "failed": 0
        }
    }

@app.get("/api/v1/connections")
async def list_connections(
    device_id: Optional[str] = None,
    link_type: Optional[str] = None,
    status: Optional[str] = None,
    limit: int = 100,
    offset: int = 0
):
    """获取连接列表"""
    return {
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }

@app.get("/api/v1/connections/{connection_id}")
async def get_connection(connection_id: str):
    """获取连接详情"""
    return {
        "id": connection_id,
        "source": {
            "device_id": "core-1",
            "device_name": "Core-SW-1",
            "port_id": "port-1",
            "port_name": "Eth1/1"
        },
        "destination": {
            "device_id": "agg-1",
            "device_name": "Agg-SW-1",
            "port_id": "port-2",
            "port_name": "Eth1/1"
        },
        "link_type": "UPLINK",
        "status": "PROPOSED",
        "score": 85.5,
        "created_at": "2024-01-15T00:00:00Z"
    }

@app.post("/api/v1/connections/validate")
async def validate_connections(request: ValidateRequest):
    """验证连接"""
    # 实际实现需要调用验证引擎
    return {
        "valid": True,
        "errors": [],
        "warnings": [
            "Module compatibility check is pending"
        ]
    }

@app.post("/api/v1/connections/explain")
async def explain_connection(connection_id: str):
    """解释连接"""
    # 实际实现需要调用解释引擎
    return {
        "connection_id": connection_id,
        "summary": "Connection from Core-SW-1 Eth1/1 to Agg-SW-1 Eth1/1",
        "rule_explanation": "Applied topology rule: core-to-aggregation-v1",
        "constraint_explanation": "All constraints satisfied",
        "scoring_explanation": "Total score 85.5 from: same_rack: 30, dac: 20, shortest_path: 15",
        "alternatives": [
            "Alternative 1: Use Eth1/2 on both devices",
            "Alternative 2: Use Agg-SW-2 instead"
        ],
        "generated_at": "2024-01-15T00:00:00Z"
    }

@app.get("/api/v1/rules")
async def list_rules(
    type: Optional[str] = None,
    enabled: Optional[bool] = None,
    limit: int = 100,
    offset: int = 0
):
    """获取规则列表"""
    return {
        "items": [],
        "total": 0,
        "limit": limit,
        "offset": offset
    }

@app.post("/api/v1/rules/reload")
async def reload_rules():
    """重新加载规则"""
    # 实际实现需要触发规则重载
    return {"status": "reloaded", "rules_loaded": 42}

@app.get("/api/v1/metrics")
async def get_metrics():
    """获取指标"""
    return {
        "connections": {"total": 100, "pending": 5, "approved": 95},
        "devices": {"total": 50, "active": 48},
        "resources": {"port_utilization": 0.75, "module_utilization": 0.60},
        "performance": {"avg_generation_time_ms": 250}
    }

@app.get("/api/v1/version")
async def get_version():
    """获取版本"""
    return {
        "version": "1.0.0",
        "build": "20240115.001",
        "api_version": "v1"
    }

@app.post("/api/v1/maintenance")
async def maintenance_operation(
    operation: str = Body(...),
    parameters: Dict[str, Any] = Body(default_factory=dict)
):
    """执行维护操作"""
    return {
        "status": "completed",
        "operation": operation,
        "result": "success"
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
```