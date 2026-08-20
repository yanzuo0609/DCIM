from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class RackStatus(str, Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class RackTemplateCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    total_u: int = Field(default=42, ge=1, le=60)
    width: int = Field(default=600, ge=400, le=1200)
    depth: int = Field(default=1000, ge=600, le=1500)
    visual_style: Literal["classic", "schematic", "realistic", "grid"] = "classic"
    description: str | None = None


class RackTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    total_u: int | None = Field(default=None, ge=1, le=60)
    width: int | None = Field(default=None, ge=400, le=1200)
    depth: int | None = Field(default=None, ge=600, le=1500)
    visual_style: Literal["classic", "schematic", "realistic", "grid"] | None = None
    description: str | None = None


class RackTemplateAppliedRoom(BaseModel):
    id: str
    name: str
    rack_count: int = 0
    room_deleted: bool = False


class RackTemplateResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    total_u: int
    width: int
    depth: int
    visual_style: str = "classic"
    description: str | None
    created_at: datetime
    updated_at: datetime
    applied_rack_count: int = 0
    applied_rooms: list[RackTemplateAppliedRoom] = Field(default_factory=list)


class ApplyTemplateToRoomRequest(BaseModel):
    room_id: str
    fill_empty_slots: bool = Field(
        default=True,
        description="为空闲机柜位创建机柜并套用模板；已有机柜更新为该模板规格",
    )
    visual_style: Literal["classic", "schematic", "realistic", "grid"] | None = Field(
        default=None,
        description="应用到机柜的视觉样式；为空则沿用模板默认样式",
    )


class ApplyTemplateToRoomResult(BaseModel):
    updated: int = 0
    created: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class UnapplyTemplateFromRoomRequest(BaseModel):
    room_id: str
    delete_empty_racks: bool = Field(
        default=True,
        description="软删除该机房内绑定此模板且无设备的机柜",
    )
    detach_template: bool = Field(
        default=True,
        description="对其余仍绑定此模板的机柜解除模板关联（保留机柜实例）",
    )


class UnapplyTemplateFromRoomResult(BaseModel):
    deleted: int = 0
    detached: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class RackBatchDeleteRequest(BaseModel):
    ids: list[str] = Field(min_length=1, description="要删除的机柜 ID 列表")


class RackBatchDeleteResult(BaseModel):
    deleted: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class PlaceBatchRequest(BaseModel):
    room_id: str
    mode: str = Field(
        default="all",
        description="all | by_row | by_column | single",
    )
    template_id: str | None = Field(
        default=None,
        description="整机房/单机柜默认模板；按排/列未指定时的回退模板",
    )
    row_templates: dict[str, str] = Field(
        default_factory=dict,
        description="按排：键为排号(1-based)，值为模板 ID",
    )
    column_templates: dict[str, str] = Field(
        default_factory=dict,
        description="按列：键为列号(1-based)，值为模板 ID",
    )
    fill_empty_slots: bool = True
    update_existing: bool = True
    row_no: int | None = Field(default=None, ge=1)
    column_no: int | None = Field(default=None, ge=1)
    code: str | None = Field(default=None, max_length=50)
    name: str | None = Field(default=None, max_length=100)


class PlaceBatchResult(BaseModel):
    updated: int = 0
    created: int = 0
    skipped: int = 0
    errors: list[str] = Field(default_factory=list)


class RackCodeConflictInfo(BaseModel):
    id: str
    code: str
    name: str
    room_id: str
    room_name: str | None = None
    row_no: int
    column_no: int


class RackCodeCheckResponse(BaseModel):
    code: str
    available: bool
    suggestion: str
    conflict: RackCodeConflictInfo | None = None


class RackCreate(BaseModel):
    room_id: str
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    rack_template_id: str | None = None
    row_no: int | None = Field(default=None, ge=1)
    column_no: int | None = Field(default=None, ge=1)
    total_u: int = Field(default=42, ge=1, le=60)
    width: int = Field(default=600, ge=400, le=1200)
    depth: int = Field(default=1000, ge=600, le=1500)
    visual_style: Literal["classic", "schematic", "realistic", "grid"] | None = None
    status: RackStatus = RackStatus.ACTIVE
    description: str | None = None


class RackUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    row_no: int | None = Field(default=None, ge=1)
    column_no: int | None = Field(default=None, ge=1)
    total_u: int | None = Field(default=None, ge=1, le=60)
    width: int | None = Field(default=None, ge=400, le=1200)
    depth: int | None = Field(default=None, ge=600, le=1500)
    visual_style: Literal["classic", "schematic", "realistic", "grid"] | None = None
    status: RackStatus | None = None
    description: str | None = None
    app_usage: str | None = Field(default=None, max_length=100)
    app_color: str | None = Field(default=None, max_length=20)


class RackResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    room_id: str
    rack_template_id: str | None
    code: str
    name: str
    seq_no: int | None = None
    row_no: int
    column_no: int
    total_u: int
    width: int
    depth: int
    visual_style: str = "classic"
    status: str
    description: str | None
    app_usage: str | None = None
    app_color: str | None = None
    occupied_u: int = 0
    free_u: int = 0
    utilization: float = 0.0
    device_count: int = 0
    total_power: float = 0.0
    created_at: datetime
    updated_at: datetime


class RackPositionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    rack_id: str
    u_position: int
    occupied: bool
    device_id: str | None


class RackLayoutDevice(BaseModel):
    device_id: str
    hostname: str
    height_u: int
    start_u: int
    power: float | None = None
    ip_summary: str | None = None
    bmc_ip: str | None = None
    vip: str | None = None
    model_name: str | None = None


class RackLayoutSlot(BaseModel):
    """One visual row in the rack cabinet (top = highest U)."""

    u_position: int
    occupied: bool
    is_span_start: bool = False
    span_height: int = 1
    device: RackLayoutDevice | None = None


class RackLayoutResponse(BaseModel):
    rack: RackResponse
    positions: list[RackPositionResponse]
    slots: list[RackLayoutSlot] = Field(default_factory=list)
    devices: list[RackLayoutDevice] = Field(default_factory=list)
    total_power: float = 0.0
