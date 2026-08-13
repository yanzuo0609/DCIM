"""Typed wiring rule config stored in network_wiring_rule.config JSON."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

FabricRole = Literal["CORE", "AGG", "ACCESS", "SERVER", "FIREWALL", "OTHER"]
ConnectionType = Literal[
    "ACCESS_ENDPOINT",
    "BMC_ENDPOINT",
    "CORE_TO_ACCESS",
    "SWITCH_INTERCONNECT",
    # legacy (accepted then migrated)
    "UPLINK",
    "DOWNLINK",
    "SERVER",
    "SECURITY",
    "PEER",
    "DAD",
    "MGMT",
]
SpeedMode = Literal["EXACT", "MIN"]
PairingMode = Literal["PER_SOURCE_TARGET", "POOL"]
PortPurpose = Literal["UPLINK", "DOWNLINK", "MGMT", "PEER", "DAD", "SERVER", "OTHER"]
PortPool = Literal["AUTO", "OPTICAL", "UPLINK"]
PortAllocation = Literal["AUTO"]
AllocationMode = Literal["AUTO", "MANUAL", "HYBRID"]
PortSelectPolicy = Literal["MIN_ASC", "MAX_DESC", "SAME_NUMBER", "SLOT_SPREAD"]
PortMediaFilter = str  # AUTO | LC_LC | MPO8 | MPO4 | FIBER | COPPER | custom
DiversityLevel = Literal["REQUIRED", "OPTIONAL", "OFF"]
RedundancyMode = Literal["NONE", "A_B"]
LagMode = Literal["STATIC", "LACP"]
DistanceMode = Literal["AUTO", "FIXED"]
CableLengthMode = Literal["AUTO", "FIXED"]
MediaKind = Literal["AUTO", "DAC", "AOC", "FIBER_SM", "FIBER_MM", "MPO", "COPPER", "BREAKOUT_1X4"]


class WiringPair(BaseModel):
    source_node_id: str
    source_port_id: str
    target_node_id: str
    target_port_id: str


class WiringRuleConfig(BaseModel):
    """Canonical config; unknown legacy keys are ignored via extra=ignore on normalize."""

    model_config = {"extra": "ignore"}

    # 01 device
    source_role: FabricRole | None = None
    target_role: FabricRole | None = None
    source_groups: list[str] = Field(default_factory=list)
    target_groups: list[str] = Field(default_factory=list)
    # legacy singular (normalized into *_groups)
    source_group: str | None = None
    target_group: str | None = None
    source_node_ids: list[str] = Field(default_factory=list)
    target_node_ids: list[str] = Field(default_factory=list)
    connection_type: ConnectionType = "CORE_TO_ACCESS"
    required: bool = True

    # 02/03 link
    link_count: int = Field(default=2, ge=1, le=128)
    min_link_count: int | None = Field(default=None, ge=0, le=128)
    max_link_count: int | None = Field(default=None, ge=1, le=512)
    speed: str | None = "100G"
    speed_mode: SpeedMode = "EXACT"
    pairing: PairingMode = "PER_SOURCE_TARGET"
    # legacy
    max_links: int | None = Field(default=None, ge=1, le=512)
    link_type: str | None = None
    cable_type: str | None = None

    # 04 ports
    source_port_purpose: PortPurpose | None = None
    target_port_purpose: PortPurpose | None = None
    # AUTO=按 purpose；OPTICAL=板卡光口(main/card)；UPLINK=40/100G 上联
    source_port_pool: PortPool | None = "AUTO"
    target_port_pool: PortPool | None = "AUTO"
    port_speed: str | None = None
    port_type: str | None = None
    source_port_types: list[str] = Field(default_factory=list)
    target_port_types: list[str] = Field(default_factory=list)
    source_port_ids: list[str] = Field(default_factory=list)
    target_port_ids: list[str] = Field(default_factory=list)
    source_port_range: str | None = None
    target_port_range: str | None = None
    peer_port_range: str | None = None
    port_allocation: PortAllocation = "AUTO"
    allocation_mode: AllocationMode = "AUTO"
    source_port_policy: PortSelectPolicy = "MIN_ASC"
    target_port_policy: PortSelectPolicy = "MIN_ASC"
    port_media: PortMediaFilter | None = "AUTO"
    port_priority: int = Field(default=100, ge=0, le=1000)

    # 05 redundancy
    redundancy_mode: RedundancyMode = "NONE"
    device_diversity: DiversityLevel = "OFF"
    path_diversity: DiversityLevel = "OFF"
    rack_diversity: DiversityLevel = "OFF"
    power_domain_diversity: DiversityLevel = "OFF"
    card_diversity: DiversityLevel = "OFF"
    port_diversity: DiversityLevel = "OFF"

    # 06 peer-link
    peer_link: bool = False
    peer_link_count: int = Field(default=2, ge=1, le=64)
    peer_link_speed: str | None = "100G"
    peer_media: MediaKind | None = "DAC"
    peer_port_purpose: PortPurpose = "PEER"
    interconnect_scope: Literal["INTRA_GROUP", "INTER_GROUP"] = "INTRA_GROUP"
    enable_peer_link: bool = True
    enable_dad: bool = True
    peer_tail_count: int = Field(default=2, ge=1, le=8)
    dad_tail_count: int = Field(default=2, ge=1, le=8)

    # 07 keepalive
    keepalive: bool = False
    keepalive_network: str | None = "OOB"

    # 08 LAG
    lag: bool = False
    lag_count: int = Field(default=1, ge=1, le=32)
    lag_mode: LagMode = "LACP"

    # 09/10 media + distance
    media: MediaKind = "AUTO"
    fiber_type: str | None = "OS2"
    connector: str | None = "LC"
    distance_mode: DistanceMode = "AUTO"
    max_distance_m: float | None = Field(default=3.0, ge=0, le=10000)
    module: str | None = None
    cable_length_mode: CableLengthMode = "AUTO"
    cable_length_m: float | None = None

    # 11 labels
    label_template: str | None = "{conn}-{seq:02d}"
    cable_code_template: str | None = None
    business_plane: str | None = None

    # 12 validation
    validate_on_apply: bool = True

    # manual pairs
    pairs: list[WiringPair] = Field(default_factory=list)

    @field_validator("source_group", "target_group", mode="before")
    @classmethod
    def empty_str_none(cls, v: object) -> object:
        if v is None:
            return None
        if isinstance(v, list):
            # tolerate accidental array on singular field
            for item in v:
                s = str(item).strip()
                if s:
                    return s
            return None
        s = str(v).strip()
        return s or None

    @field_validator("source_groups", "target_groups", mode="before")
    @classmethod
    def coerce_group_lists(cls, v: object) -> object:
        if v is None:
            return []
        if isinstance(v, str):
            s = v.strip()
            return [s] if s else []
        if isinstance(v, list):
            out: list[str] = []
            for item in v:
                s = str(item).strip()
                if s and s not in out:
                    out.append(s)
            return out
        return []

    @model_validator(mode="before")
    @classmethod
    def merge_legacy_groups(cls, data: Any) -> Any:
        if not isinstance(data, dict):
            return data
        data = dict(data)
        data["connection_type"] = _migrate_connection_type(data.get("connection_type"))
        for side in ("source", "target"):
            plural = f"{side}_groups"
            singular = f"{side}_group"
            groups: list[str] = []
            raw = data.get(plural)
            if isinstance(raw, list):
                for item in raw:
                    s = str(item).strip()
                    if s and s not in groups:
                        groups.append(s)
            elif isinstance(raw, str) and raw.strip():
                groups.append(raw.strip())
            legacy = data.get(singular)
            if not groups and legacy is not None:
                if isinstance(legacy, list):
                    for item in legacy:
                        s = str(item).strip()
                        if s and s not in groups:
                            groups.append(s)
                else:
                    s = str(legacy).strip()
                    if s:
                        groups.append(s)
            data[plural] = groups
            data[singular] = groups[0] if groups else None
        return data

    @model_validator(mode="after")
    def normalize_counts(self) -> WiringRuleConfig:
        # legacy max_links → max_link_count
        if self.max_link_count is None and self.max_links is not None:
            self.max_link_count = self.max_links
        if self.max_link_count is None:
            self.max_link_count = max(self.link_count, 256 if self.max_links is None else self.max_links)
        if self.min_link_count is None:
            self.min_link_count = self.link_count
        if self.min_link_count > self.link_count:
            self.min_link_count = self.link_count
        if self.max_link_count < self.link_count:
            self.max_link_count = self.link_count
        self.connection_type = _migrate_connection_type(self.connection_type)
        # default purposes from connection type
        if self.source_port_purpose is None:
            self.source_port_purpose = _default_purpose(self.connection_type, "source")
        if self.target_port_purpose is None:
            self.target_port_purpose = _default_purpose(self.connection_type, "target")
        if self.port_speed is None and self.speed:
            self.port_speed = self.speed
        if self.source_port_pool is None:
            self.source_port_pool = _pool_from_purpose(self.source_port_purpose)
        if self.target_port_pool is None:
            self.target_port_pool = _pool_from_purpose(self.target_port_purpose)
        # allocation_mode 兼容旧 port_allocation
        mode = str(self.allocation_mode or self.port_allocation or "AUTO").upper()
        if mode not in ("AUTO", "MANUAL", "HYBRID"):
            mode = "AUTO"
        self.allocation_mode = mode  # type: ignore[assignment]
        if self.port_media is None:
            self.port_media = "AUTO"
        if self.peer_link or self.connection_type == "SWITCH_INTERCONNECT":
            self.peer_link = True
            self.connection_type = "SWITCH_INTERCONNECT"
            self.source_port_purpose = "PEER"
            self.target_port_purpose = "PEER"
            self.source_port_pool = "UPLINK"
            self.target_port_pool = "UPLINK"
            self.link_count = self.peer_link_count
            if self.peer_link_speed:
                self.speed = self.peer_link_speed
                self.port_speed = self.peer_link_speed
            if self.peer_media:
                self.media = self.peer_media
        return self


_LEGACY_CONNECTION_MAP = {
    "UPLINK": "CORE_TO_ACCESS",
    "DOWNLINK": "CORE_TO_ACCESS",
    "SERVER": "ACCESS_ENDPOINT",
    "SECURITY": "ACCESS_ENDPOINT",
    "PEER": "SWITCH_INTERCONNECT",
    "DAD": "SWITCH_INTERCONNECT",
    "MGMT": "BMC_ENDPOINT",
}


def _migrate_connection_type(raw: object) -> ConnectionType:
    v = str(raw or "").strip() or "CORE_TO_ACCESS"
    if v in (
        "ACCESS_ENDPOINT",
        "BMC_ENDPOINT",
        "CORE_TO_ACCESS",
        "SWITCH_INTERCONNECT",
    ):
        return v  # type: ignore[return-value]
    return _LEGACY_CONNECTION_MAP.get(v, "CORE_TO_ACCESS")  # type: ignore[return-value]


def _default_purpose(conn: ConnectionType, side: str) -> PortPurpose:
    c = _migrate_connection_type(conn)
    if c == "CORE_TO_ACCESS":
        # 核心/汇聚板卡口 → 接入 UPLINK
        return "DOWNLINK" if side == "source" else "UPLINK"
    if c == "ACCESS_ENDPOINT":
        return "DOWNLINK" if side == "source" else "SERVER"
    if c == "BMC_ENDPOINT":
        return "MGMT"
    if c == "SWITCH_INTERCONNECT":
        return "PEER"
    return "OTHER"


def _pool_from_purpose(purpose: PortPurpose | None) -> PortPool:
    if purpose in ("UPLINK", "PEER", "DAD"):
        return "UPLINK"
    if purpose in ("DOWNLINK", "SERVER"):
        return "OPTICAL"
    return "AUTO"


CONNECTION_TO_LINK_ROLE: dict[str, str] = {
    "ACCESS_ENDPOINT": "server",
    "BMC_ENDPOINT": "mgmt",
    "CORE_TO_ACCESS": "uplink",
    "SWITCH_INTERCONNECT": "interconnect",
    "UPLINK": "uplink",
    "DOWNLINK": "downlink",
    "SERVER": "server",
    "SECURITY": "security",
    "PEER": "interconnect",
    "DAD": "interconnect",
    "MGMT": "mgmt",
}

CONNECTION_TO_LINK_TYPE: dict[str, str] = {
    "ACCESS_ENDPOINT": "switch_server",
    "BMC_ENDPOINT": "switch_server",
    "CORE_TO_ACCESS": "switch_switch",
    "SWITCH_INTERCONNECT": "switch_switch",
    "UPLINK": "switch_switch",
    "DOWNLINK": "switch_switch",
    "SERVER": "switch_server",
    "SECURITY": "switch_security",
    "PEER": "switch_switch",
    "DAD": "switch_switch",
    "MGMT": "switch_switch",
}


def normalize_wiring_config(raw: dict[str, Any] | None) -> dict[str, Any]:
    """Validate and fill defaults; return JSON-serializable dict."""
    data = dict(raw or {})
    # legacy: only max_links without link_count
    if "link_count" not in data and data.get("max_links"):
        data["link_count"] = min(int(data["max_links"]), 2)
    cfg = WiringRuleConfig.model_validate(data)
    return cfg.model_dump(mode="json")
