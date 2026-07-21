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
