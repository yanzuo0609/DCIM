from __future__ import annotations

import uuid
from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


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
    # 与 SlotInterfaceGroup.count 上限对齐；blank/raid 可为 0
    port_count: int = Field(default=1, ge=0, le=128)


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
    layout_w: float | None = Field(default=None, ge=20, le=800)
    layout_h: float | None = Field(default=None, ge=20, le=800)
    server_slot_kind: str | None = Field(default=None, max_length=20)
    orientation: Literal["horizontal", "vertical"] | None = None
    zone_label: str | None = Field(default=None, max_length=40)
    zone_layout: Literal["single_row", "two_row", "auto"] | None = None
    # 兼容旧字段；实际上接口数以 groups 为准
    port_count: int | None = Field(default=None, ge=0, le=128)
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
    peer_device_id: uuid.UUID | None = Field(
        default=None, description="对端台账设备 ID（设备管理）"
    )
    peer_device_name: str | None = Field(
        default=None, max_length=200, description="对端台账设备展示名缓存"
    )
    layout_locked: bool | None = None
    # 布线用途：UPLINK / SERVER / PEER / MGMT / DOWNLINK / OTHER
    purpose: str | None = Field(default=None, max_length=20)
    reserved: bool | None = None
    port_group: str | None = Field(default=None, max_length=50)


class CoreLineCard(BaseModel):
    id: str = Field(min_length=1, max_length=50)
    card_type: Literal["gigabit", "ten_gigabit", "100g", "blank"] = "ten_gigabit"
    port_count: int = Field(default=48, ge=0, le=128)


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
    uplink_port_count: int | None = Field(default=None, ge=0, le=128)
    line_cards: list[CoreLineCard] | None = None
    server_form_factor: Literal[1, 2, 4] | None = None
    server_panel_side: Literal["front", "rear"] | None = None
    server_onboard_1g_count: int | None = Field(default=None, ge=0, le=8)
    security_panel: bool | None = None
    layout_locked: bool | None = None


def default_slots() -> list[SlotConfig]:
    return [SlotConfig() for _ in range(8)]


class NetworkTopologyCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str | None = None
    project_id: uuid.UUID | None = None


class NetworkTopologyUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = None
    project_id: uuid.UUID | None = None


class NetworkTopologyResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    project_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NetworkDeviceBrief(BaseModel):
    device_id: uuid.UUID
    name: str | None
    hostname: str
    rack_id: uuid.UUID | None = None
    room_id: uuid.UUID | None = None
    rack_code: str | None
    room_name: str | None
    u_position: int | None
    ip_summary: str | None
    bmc_ip: str | None
    vip: str | None
    device_type_name: str | None
    device_type_code: str | None = None
    device_model_name: str | None = None
    height_u: int | None = None


class NetworkNodeResponse(BaseModel):
    id: uuid.UUID
    topology_id: uuid.UUID
    kind: NetworkNodeKind
    name: str
    device_id: uuid.UUID | None
    device_model_id: uuid.UUID | None = None
    design_model_id: uuid.UUID | None = None
    contract_device_name: str | None = None
    network_role: str | None = None
    device_group: str | None = None
    device_groups: list[str] | None = None
    pos_x: float
    pos_y: float
    switch_port_count: int
    slots: list[SlotConfig] | None
    port_layout: PortLayout | None = None
    on_canvas: bool = True
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
    source_label: str | None = None
    target_label: str | None = None
    cable_type: str | None = None
    interface_class: str | None = None
    link_role: str | None = None
    connection_type: str | None = None
    speed: str | None = None
    lag_group: str | None = None
    redundancy_path: str | None = None
    media: str | None = None
    module: str | None = None
    cable_length_m: float | None = None
    wiring_rule_id: uuid.UUID | None = None
    line_style: str | None = None

    model_config = {"from_attributes": True}


class NetworkTopologyDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    description: str | None
    project_id: uuid.UUID | None = None
    nodes: list[NetworkNodeResponse]
    links: list[NetworkLinkResponse]
    created_at: datetime
    updated_at: datetime


class NetworkProjectCreate(BaseModel):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    model_root_folder_id: uuid.UUID | None = None


class NetworkProjectUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None
    model_root_folder_id: uuid.UUID | None = None


class NetworkProjectResponse(BaseModel):
    id: uuid.UUID
    code: str
    name: str
    description: str | None
    topology_id: uuid.UUID | None = None
    model_root_folder_id: uuid.UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


def _clamp_int(value: object, lo: int, hi: int, default: int | None = None) -> int | None:
    if value is None:
        return default
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(lo, min(hi, n))


def _sanitize_canvas_node_payload(data: object) -> object:
    """校验前清洗节点 payload，避免陈旧/超限 port_count 导致 422。"""
    if not isinstance(data, dict):
        return data
    node = dict(data)

    spc = _clamp_int(node.get("switch_port_count"), 1, 128, 48)
    if spc is not None:
        node["switch_port_count"] = spc

    # 丢弃节点级误传的 port_count（非 schema 字段，但部分客户端会带上）
    node.pop("port_count", None)

    slots = node.get("slots")
    if isinstance(slots, list):
        cleaned_slots = []
        for item in slots[:8]:
            if not isinstance(item, dict):
                continue
            count = _clamp_int(item.get("port_count"), 0, 128, 1) or 0
            cleaned_slots.append(
                {
                    "enabled": bool(item.get("enabled")) and count > 0,
                    "port_count": count if count > 0 else 1,
                }
            )
        while len(cleaned_slots) < 8:
            cleaned_slots.append({"enabled": False, "port_count": 1})
        node["slots"] = cleaned_slots

    layout = node.get("port_layout")
    if isinstance(layout, dict):
        layout = dict(layout)
        for key, lo, hi, default in (
            ("rack_width_mm", 400, 1200, 600),
            ("main_port_count", 1, 128, None),
            ("uplink_port_count", 0, 128, None),
            ("server_onboard_1g_count", 0, 8, None),
            ("slot_count", 0, 256, None),
        ):
            if key in layout and layout[key] is not None:
                layout[key] = _clamp_int(layout[key], lo, hi, default)

        slots_def = layout.get("slots_def")
        if isinstance(slots_def, list):
            cleaned_defs = []
            for slot in slots_def:
                if not isinstance(slot, dict):
                    continue
                slot = dict(slot)
                # 废弃字段：有 groups 时删除，避免旧 le=32 或冲突
                groups = slot.get("groups")
                if isinstance(groups, list) and groups:
                    slot.pop("port_count", None)
                    slot.pop("port_types", None)
                    slot.pop("default_port_type", None)
                    cleaned_groups = []
                    for g in groups:
                        if not isinstance(g, dict):
                            continue
                        g = dict(g)
                        g["count"] = _clamp_int(g.get("count"), 1, 128, 1) or 1
                        cleaned_groups.append(g)
                    slot["groups"] = cleaned_groups
                else:
                    # blank / 无 groups
                    if "port_count" in slot and slot["port_count"] is not None:
                        slot["port_count"] = _clamp_int(slot["port_count"], 0, 128, 0)
                    slot["groups"] = [] if slot.get("server_slot_kind") in ("blank", "raid") else (groups or [])
                if slot.get("layout_w") is not None:
                    slot["layout_w"] = _clamp_int(slot["layout_w"], 20, 800, 40)
                if slot.get("layout_h") is not None:
                    slot["layout_h"] = _clamp_int(slot["layout_h"], 20, 800, 40)
                cleaned_defs.append(slot)
            layout["slots_def"] = cleaned_defs

        ports = layout.get("ports")
        if isinstance(ports, list):
            cleaned_ports = []
            for p in ports:
                if not isinstance(p, dict):
                    continue
                p = dict(p)
                if p.get("w") is not None:
                    p["w"] = float(_clamp_int(p["w"], 8, 120, 12) or 12)
                if p.get("h") is not None:
                    p["h"] = float(_clamp_int(p["h"], 8, 60, 10) or 10)
                cleaned_ports.append(p)
            layout["ports"] = cleaned_ports

        line_cards = layout.get("line_cards")
        if isinstance(line_cards, list):
            cleaned_cards = []
            for c in line_cards:
                if not isinstance(c, dict):
                    continue
                c = dict(c)
                if c.get("card_type") == "blank":
                    c["port_count"] = 0
                else:
                    c["port_count"] = _clamp_int(c.get("port_count"), 1, 128, 48) or 48
                cleaned_cards.append(c)
            layout["line_cards"] = cleaned_cards

        node["port_layout"] = layout

        # 有可视化布局时忽略客户端 slots，改由 after 校验器派生
        if layout.get("slots_def"):
            node["slots"] = None

    return node


class CanvasNodeInput(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: uuid.UUID | None = None
    kind: NetworkNodeKind
    name: str = Field(min_length=1, max_length=200)
    device_id: uuid.UUID | None = None
    device_model_id: uuid.UUID | None = None
    design_model_id: uuid.UUID | None = None
    contract_device_name: str | None = Field(default=None, max_length=100)
    network_role: str | None = Field(default=None, max_length=20)
    device_group: str | None = Field(default=None, max_length=80)
    device_groups: list[str] | None = None
    pos_x: float = 100.0
    pos_y: float = 100.0
    switch_port_count: int = Field(default=48, ge=1, le=128)
    slots: list[SlotConfig] | None = None
    port_layout: PortLayout | None = None
    on_canvas: bool = True

    @model_validator(mode="before")
    @classmethod
    def sanitize_payload(cls, data: object) -> object:
        return _sanitize_canvas_node_payload(data)

    @model_validator(mode="after")
    def validate_node(self) -> CanvasNodeInput:
        # 归一多组：从 device_groups / device_group 合并，并回写首组到 device_group
        groups: list[str] = []
        seen: set[str] = set()

        def _push(raw: object) -> None:
            if isinstance(raw, list):
                for item in raw:
                    s = str(item or "").strip()
                    if s and s not in seen:
                        seen.add(s)
                        groups.append(s)
            elif isinstance(raw, str) and raw.strip():
                for part in raw.replace(";", ",").split(","):
                    s = part.strip()
                    if s and s not in seen:
                        seen.add(s)
                        groups.append(s)

        _push(self.device_groups)
        _push(self.device_group)
        self.device_groups = groups or None
        self.device_group = groups[0] if groups else None

        if self.port_layout and self.port_layout.slots_def:
            self.slots = _slots_from_layout_def(self.port_layout.slots_def)
        elif self.kind in (NetworkNodeKind.SERVER, NetworkNodeKind.SECURITY):
            slots = self.slots or default_slots()
            if len(slots) != 8:
                raise ValueError("slots must contain exactly 8 entries")
            self.slots = slots
        else:
            self.slots = None
        if self.contract_device_name is not None:
            name = self.contract_device_name.strip()
            self.contract_device_name = name or None
        return self


def _slot_port_count(item: LayoutSlotDef) -> int:
    if item.groups:
        return sum(g.count for g in item.groups)
    return item.port_count or 0


def _slots_from_layout_def(slots_def: list[LayoutSlotDef]) -> list[SlotConfig]:
    """将可视化 slots_def 映射为旧版 8 槽 SlotConfig（blank/raid 等 0 口槽为 disabled）。"""
    slots = [SlotConfig() for _ in range(8)]
    for idx, item in enumerate(slots_def[:8]):
        count = _slot_port_count(item)
        if count <= 0:
            slots[idx] = SlotConfig(enabled=False, port_count=1)
        else:
            slots[idx] = SlotConfig(enabled=True, port_count=min(128, max(1, count)))
    return slots


class CanvasLinkInput(BaseModel):
    id: uuid.UUID | None = None
    link_type: NetworkLinkType
    source_node_id: uuid.UUID
    source_port: str = Field(min_length=1, max_length=50)
    target_node_id: uuid.UUID
    target_port: str = Field(min_length=1, max_length=50)
    label: str | None = Field(default=None, max_length=200)
    source_label: str | None = Field(default=None, max_length=200)
    target_label: str | None = Field(default=None, max_length=200)
    cable_type: str | None = Field(default=None, max_length=30)
    interface_class: str | None = Field(default=None, max_length=30)
    link_role: str | None = Field(default=None, max_length=30)
    connection_type: str | None = Field(default=None, max_length=30)
    speed: str | None = Field(default=None, max_length=20)
    lag_group: str | None = Field(default=None, max_length=80)
    redundancy_path: str | None = Field(default=None, max_length=10)
    media: str | None = Field(default=None, max_length=30)
    module: str | None = Field(default=None, max_length=80)
    cable_length_m: float | None = None
    wiring_rule_id: uuid.UUID | None = None
    line_style: str | None = Field(default=None, max_length=40)


class CanvasSaveRequest(BaseModel):
    nodes: list[CanvasNodeInput]
    links: list[CanvasLinkInput]


class NetworkLabSessionResponse(BaseModel):
    id: uuid.UUID
    topology_id: uuid.UUID
    engine: str
    external_lab_path: str | None = None
    status: str
    last_sync_at: datetime | None = None
    error_message: str | None = None
    node_map: dict[str, str] | None = None
    node_status: dict[str, str] | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class LabEngineInfoResponse(BaseModel):
    engine: str
    configured: bool
    base_url: str | None = None
    message: str | None = None


class LabConsoleResponse(BaseModel):
    node_id: uuid.UUID
    console_url: str | None = None
    message: str | None = None
