from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


BindType = Literal["none", "device", "rack", "rack_range"]
IpStatusLiteral = Literal["free", "allocated", "disabled", "reserved"]


class IpAddressCreate(BaseModel):
    system_ip: str = Field(min_length=3, max_length=64)
    bmc_ip: str | None = Field(default=None, max_length=64)
    vip: str | None = Field(default=None, max_length=64)
    netmask: str | None = Field(default=None, max_length=64)
    gateway: str | None = Field(default=None, max_length=64)
    dns: str | None = Field(default=None, max_length=64)
    dns_secondary: str | None = Field(default=None, max_length=64)
    label: str | None = Field(default=None, max_length=100)
    description: str | None = None
    status: IpStatusLiteral = Field(default="free", description="初始状态，默认空闲")


class IpAddressUpdate(BaseModel):
    system_ip: str | None = Field(default=None, min_length=3, max_length=64)
    bmc_ip: str | None = Field(default=None, max_length=64)
    vip: str | None = Field(default=None, max_length=64)
    netmask: str | None = Field(default=None, max_length=64)
    gateway: str | None = Field(default=None, max_length=64)
    dns: str | None = Field(default=None, max_length=64)
    dns_secondary: str | None = Field(default=None, max_length=64)
    label: str | None = Field(default=None, max_length=100)
    description: str | None = None
    status: IpStatusLiteral | None = Field(
        default=None, description="手动设置：disabled/reserved/free；free 启用后按绑定回填"
    )


class IpAddressResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    system_ip: str
    bmc_ip: str | None
    vip: str | None
    netmask: str | None = None
    gateway: str | None = None
    dns: str | None = None
    dns_secondary: str | None = None
    label: str | None
    description: str | None
    status: str = "free"
    segment_id: str | None = None
    bind_type: str
    device_id: str | None
    device_name: str | None = None
    rack_id: str | None
    rack_code: str | None = None
    room_id: str | None
    room_name: str | None = None
    scope_rack_ids: list[str] | None = None
    u_position: int | None
    created_at: datetime
    updated_at: datetime


class IpStatusBatchRequest(BaseModel):
    ids: list[str] = Field(min_length=1)
    status: IpStatusLiteral


class IpStatusBatchResult(BaseModel):
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class IpAddressBatchCreateRequest(BaseModel):
    """按系统 IP 段批量生成记录，同时创建/归属到一个地址段。"""

    name: str | None = Field(default=None, max_length=100, description="地址段名称，默认用起止 IP")
    start_system_ip: str
    end_system_ip: str
    start_bmc_ip: str | None = None
    netmask: str | None = Field(default=None, max_length=64, description="子网掩码，如 255.255.255.0 或 /24")
    gateway: str | None = Field(default=None, max_length=64)
    dns: str | None = Field(default=None, max_length=64)
    dns_secondary: str | None = Field(default=None, max_length=64)
    application_type: str | None = Field(default=None, max_length=50, description="应用类型")
    label_prefix: str | None = None
    description: str | None = None


class IpAddressBatchCreateResult(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    segment_id: str | None = None


class IpSegmentCreate(BaseModel):
    """按参考台账新建地址段：网络地址 + 掩码位数，自动展开主机地址。"""

    application: str | None = Field(default=None, max_length=100, description="应用")
    network: str = Field(description="IP地址段，如 172.17.0.0")
    prefix_len: int = Field(default=24, ge=8, le=30, description="掩码位数，如 24")
    gateway: str | None = Field(default=None, max_length=64)
    reserved_count: int = Field(default=0, ge=0, description="保留个数")
    address_purpose: str | None = Field(default=None, max_length=50, description="地址用途")
    network_type: str | None = Field(default=None, max_length=50, description="网络类型")
    location: str | None = Field(default=None, max_length=100, description="所属机房位置")
    remarks: str | None = Field(default=None, description="备注")
    start_bmc_ip: str | None = None
    dns: str | None = Field(default=None, max_length=64)
    dns_secondary: str | None = Field(default=None, max_length=64)


class IpSegmentUpdate(BaseModel):
    application: str | None = Field(default=None, max_length=100)
    gateway: str | None = Field(default=None, max_length=64)
    address_purpose: str | None = Field(default=None, max_length=50)
    network_type: str | None = Field(default=None, max_length=50)
    location: str | None = Field(default=None, max_length=100)
    remarks: str | None = None
    dns: str | None = Field(default=None, max_length=64)
    dns_secondary: str | None = Field(default=None, max_length=64)
    # 兼容旧编辑表单
    name: str | None = Field(default=None, min_length=1, max_length=100)
    netmask: str | None = Field(default=None, max_length=64)
    application_type: str | None = Field(default=None, max_length=50)
    label: str | None = Field(default=None, max_length=100)
    description: str | None = None


class IpSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    application: str | None = None
    network: str
    prefix_len: int = 24
    gateway: str | None = None
    address_purpose: str | None = None
    network_type: str | None = None
    location: str | None = None
    remarks: str | None = None
    # 统计
    total_count: int = 0
    free_count: int = 0
    allocated_count: int = 0
    reserved_count: int = 0
    disabled_count: int = 0
    # 兼容
    name: str
    start_ip: str
    end_ip: str
    netmask: str | None = None
    dns: str | None = None
    dns_secondary: str | None = None
    application_type: str | None = None
    label: str | None = None
    description: str | None = None
    created_at: datetime
    updated_at: datetime


class IpSegmentDetail(IpSegmentResponse):
    addresses: list[IpAddressResponse] = Field(default_factory=list)


class IpBindRequest(BaseModel):
    """手动关联：单设备 / 单机柜 / 机柜范围。"""

    bind_type: BindType
    device_id: str | None = None
    rack_id: str | None = None
    room_id: str | None = None
    rack_ids: list[str] = Field(default_factory=list)


class IpBindBatchRequest(BaseModel):
    ids: list[str] = Field(min_length=1)
    bind: IpBindRequest


class IpBindBatchResult(BaseModel):
    updated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class IpAllocateRequest(BaseModel):
    """批量选择 IP，按机柜范围从小地址→小柜号→低 U 分配，设备间隔 1U。"""

    ip_ids: list[str] = Field(min_length=1)
    room_id: str
    rack_ids: list[str] = Field(default_factory=list)
    row_nos: list[int] = Field(default_factory=list)
    column_nos: list[int] = Field(default_factory=list)


class IpAllocateAssignment(BaseModel):
    ip_id: str
    system_ip: str
    device_id: str
    device_name: str | None = None
    rack_id: str
    rack_code: str
    u_position: int


class IpAllocateResult(BaseModel):
    allocated: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
    assignments: list[IpAllocateAssignment] = Field(default_factory=list)


class IpBatchDeleteRequest(BaseModel):
    ids: list[str] = Field(min_length=1)


class IpBatchDeleteResult(BaseModel):
    deleted: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)
