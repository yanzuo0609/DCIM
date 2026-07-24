from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator


class NetworkNodeKind(str, Enum):
    SWITCH = "switch"
    SERVER = "server"
    SECURITY = "security"


class NetworkLinkType(str, Enum):
    SWITCH_SERVER = "switch_server"
    SWITCH_SWITCH = "switch_switch"
    SWITCH_SECURITY = "switch_security"


class SlotConfig(BaseModel):
    enabled: bool = False
    port_count: int = Field(default=1, ge=1, le=32)


class SlotInterfaceGroup(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    port_type: str = Field(default="1g", max_length=20)
    count: int = Field(default=1, ge=1, le=128)
    layout_order: int | None = None
    role: str | None = Field(default=None, max_length=20)
    grid_cols: int | None = Field(default=None, ge=1, le=48)
    layout_x: float | None = None
    layout_y: float | None = None


class LayoutSlotDef(BaseModel):
    groups: list[SlotInterfaceGroup] = Field(default_factory=list)
    layout_x: float | None = None
    layout_y: float | None = None
    layout_w: float | None = Field(default=None, ge=20, le=400)
    layout_h: float | None = Field(default=None, ge=20, le=400)
    server_slot_kind: str | None = Field(default=None, max_length=20)
    orientation: Literal["horizontal", "vertical"] | None = None
    port_count: int | None = Field(default=None, ge=1, le=32)
    default_port_type: str | None = Field(default=None, max_length=20)
    port_types: list[str] | None = None


class FramePort(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    label: str = Field(min_length=1, max_length=50)
    x: float = 0
    y: float = 0
    w: float = Field(default=32, ge=8, le=120)
    h: float = Field(default=14, ge=8, le=60)
    port_type: str = Field(default="1g", max_length=20)
    slot_index: int | None = Field(default=None, ge=0, le=256)
    group_id: str | None = Field(default=None, max_length=50)
    peer_node_id: uuid.UUID | None = None
    peer_port: str | None = Field(default=None, max_length=50)
    peer_label: str | None = Field(default=None, max_length=200)
    layout_locked: bool | None = None


class CoreLineCard(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    card_type: Literal["gigabit", "ten_gigabit", "100g"] = "ten_gigabit"
    port_count: int = Field(default=48, ge=1, le=128)


class PortLayout(BaseModel):
    frame_width: float = Field(default=360, ge=80, le=4000)
    frame_height: float = Field(default=49, ge=40, le=4000)
    rack_width_mm: float = Field(default=600, ge=400, le=1200)
    height_u: float = Field(default=1, ge=1, le=16)
    slot_count: int = Field(default=1, ge=0, le=256)
    slots_def: list[LayoutSlotDef] = Field(default_factory=list)
    ports: list[FramePort] = Field(default_factory=list)
    switch_subtype: str | None = Field(default=None, max_length=20)
    uplink_position: Literal["right", "middle"] | None = None
    main_port_count: int | None = Field(default=None, ge=1, le=128)
    uplink_port_count: int | None = Field(default=None, ge=0, le=32)
    line_cards: list[CoreLineCard] | None = None
    server_form_factor: Literal[1, 2, 4] | None = None
    server_panel_side: Literal["front", "rear"] | None = None
    server_onboard_1g_count: int | None = Field(default=None, ge=0, le=8)
    layout_locked: bool | None = None


def default_slots() -> list[SlotConfig]:
    return [SlotConfig() for _ in range(8)]


class NetworkTopologyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None


class NetworkTopologyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None


class NetworkTopologyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NetworkDeviceBrief(BaseModel):
    device_id: uuid.UUID
    name: str | None
    hostname: str
    rack_code: str | None
    room_name: str | None
    u_position: int | None
    ip_summary: str | None
    bmc_ip: str | None
    vip: str | None
    device_type_name: str | None


class NetworkNodeResponse(BaseModel):
    id: uuid.UUID
    topology_id: uuid.UUID
    kind: NetworkNodeKind
    name: str
    device_id: uuid.UUID | None
    pos_x: float
    pos_y: float
    switch_port_count: int
    slots: list[SlotConfig] | None
    port_layout: PortLayout | None = None
    device: NetworkDeviceBrief | None = None

    model_config = {"from_attributes": True}


class NetworkLinkResponse(BaseModel):
    id: uuid.UUID
    topology_id: uuid.UUID
    link_type: NetworkLinkType
    source_node_id: uuid.UUID
    source_port: str
    target_node_id: uuid.UUID
    target_port: str
    label: str | None

    model_config = {"from_attributes": True}


class NetworkTopologyDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    nodes: list[NetworkNodeResponse]
    links: list[NetworkLinkResponse]
    created_at: datetime
    updated_at: datetime


class CanvasNodeInput(BaseModel):
    id: uuid.UUID | None = None
    kind: NetworkNodeKind
    name: str = Field(min_length=1, max_length=200)
    device_id: uuid.UUID | None = None
    pos_x: float = 100.0
    pos_y: float = 100.0
    switch_port_count: int = Field(default=48, ge=1, le=128)
    slots: list[SlotConfig] | None = None
    port_layout: PortLayout | None = None

    @model_validator(mode="after")
    def validate_node(self) -> CanvasNodeInput:
        if self.port_layout and self.port_layout.slots_def:
            self.slots = _slots_from_layout_def(self.port_layout.slots_def)
        elif self.kind in (NetworkNodeKind.SERVER, NetworkNodeKind.SECURITY):
            slots = self.slots or default_slots()
            if len(slots) != 8:
                raise ValueError("slots must contain exactly 8 entries")
            self.slots = slots
        else:
            self.slots = None
        return self


def _slot_port_count(item: LayoutSlotDef) -> int:
    if item.groups:
        return sum(g.count for g in item.groups)
    return item.port_count or 0


def _slots_from_layout_def(slots_def: list[LayoutSlotDef]) -> list[SlotConfig]:
    slots = [SlotConfig() for _ in range(8)]
    for idx, item in enumerate(slots_def[:8]):
        slots[idx] = SlotConfig(enabled=True, port_count=_slot_port_count(item))
    return slots


class CanvasLinkInput(BaseModel):
    id: uuid.UUID | None = None
    link_type: NetworkLinkType
    source_node_id: uuid.UUID
    source_port: str = Field(min_length=1, max_length=50)
    target_node_id: uuid.UUID
    target_port: str = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=200)


class CanvasSaveRequest(BaseModel):
    nodes: list[CanvasNodeInput]
    links: list[CanvasLinkInput]
