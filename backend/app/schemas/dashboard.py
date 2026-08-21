from datetime import datetime

from pydantic import BaseModel, Field


class DashboardSummary(BaseModel):
    datacenter_count: int = 0
    room_count: int = 0
    rack_count: int = 0
    device_count: int = 0
    mounted_device_count: int = 0
    total_u: int = 0
    occupied_u: int = 0
    free_u: int = 0
    utilization: float = 0.0
    total_power: float = 0.0


class UtilizationItem(BaseModel):
    rack_id: str
    rack_code: str
    rack_name: str
    room_id: str
    total_u: int
    occupied_u: int
    utilization: float


class DashboardUtilization(BaseModel):
    items: list[UtilizationItem] = Field(default_factory=list)


class NamedMetric(BaseModel):
    name: str
    value: float
    code: str | None = None


class DualMetric(BaseModel):
    """品类在线：正常 / 异常。"""

    name: str
    normal: float = 0
    abnormal: float = 0
    code: str | None = None


class TrendPoint(BaseModel):
    label: str
    value: float


class DeviceRuntimeStats(BaseModel):
    total: int = 0
    running: int = 0
    fault: int = 0
    offline: int = 0
    repair: int = 0
    running_ratio: float = 0.0


class NetworkScreenStats(BaseModel):
    project_count: int = 0
    topology_count: int = 0
    node_count: int = 0
    link_count: int = 0


class ContractScreenStats(BaseModel):
    contract_count: int = 0
    purchase_quantity: int = 0
    linked_count: int = 0
    summary_rows: int = 0


class AlertRecord(BaseModel):
    code: str
    device_name: str
    event_time: str
    value: str | None = None


class DashboardAnalytics(BaseModel):
    """运营大屏 / 驾驶舱聚合数据。"""

    summary: DashboardSummary
    utilization: DashboardUtilization
    device_by_type: list[NamedMetric] = Field(default_factory=list)
    device_by_status: list[NamedMetric] = Field(default_factory=list)
    rack_util_buckets: list[NamedMetric] = Field(default_factory=list)
    power_by_room: list[NamedMetric] = Field(default_factory=list)
    power_by_rack: list[NamedMetric] = Field(default_factory=list)
    devices_by_datacenter: list[NamedMetric] = Field(default_factory=list)
    device_trend: list[TrendPoint] = Field(default_factory=list)
    type_online_status: list[DualMetric] = Field(default_factory=list)
    runtime: DeviceRuntimeStats = Field(default_factory=DeviceRuntimeStats)
    alert_racks: list[UtilizationItem] = Field(default_factory=list)
    alert_records: list[AlertRecord] = Field(default_factory=list)
    mount_ratio: float = 0.0
    network: NetworkScreenStats = Field(default_factory=NetworkScreenStats)
    contract: ContractScreenStats = Field(default_factory=ContractScreenStats)
    generated_at: datetime | None = None


class RoomMonitorOption(BaseModel):
    id: str
    name: str
    datacenter_name: str | None = None
    location: str | None = None
    rack_count: int = 0


class RoomMonitorRack(BaseModel):
    id: str
    code: str
    name: str
    row_no: int
    column_no: int
    total_u: int
    occupied_u: int = 0
    utilization: float = 0.0
    device_count: int = 0
    online_device_count: int = 0
    app_usage: str | None = None
    status: str = "active"


class RoomMonitorLayout(BaseModel):
    room_id: str
    room_name: str
    datacenter_name: str | None = None
    location: str | None = None
    rack_rows: int = 0
    rack_columns: int = 0
    row_layout: list[int] = Field(default_factory=list)
    slot_codes: list[list[str]] = Field(default_factory=list)
    code_prefix: str | None = "A"
    code_mode: str | None = "auto"
    pillar_layout: dict | None = None
    racks: list[RoomMonitorRack] = Field(default_factory=list)
