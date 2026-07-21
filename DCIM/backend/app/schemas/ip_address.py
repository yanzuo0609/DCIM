from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


BindType = Literal["none", "device", "rack", "rack_range"]
IpStatusLiteral = Literal["free", "allocated", "disabled"]


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
    status: IpStatusLiteral | None = Field(default=None, description="手动设置：disabled 禁用；free 启用后按绑定回填")


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
    """按系统 IP 段批量生成记录，可选同步生成 BMC IP 段。"""

    start_system_ip: str
    end_system_ip: str
    start_bmc_ip: str | None = None
    netmask: str | None = Field(default=None, max_length=64, description="子网掩码，如 255.255.255.0 或 /24")
    gateway: str | None = Field(default=None, max_length=64)
    dns: str | None = Field(default=None, max_length=64)
    dns_secondary: str | None = Field(default=None, max_length=64)
    label_prefix: str | None = None
    description: str | None = None


class IpAddressBatchCreateResult(BaseModel):
    created: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


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
