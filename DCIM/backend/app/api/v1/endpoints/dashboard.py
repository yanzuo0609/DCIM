import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_dashboard_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.dashboard import (
    DashboardAnalytics,
    DashboardSummary,
    DashboardUtilization,
    RoomMonitorLayout,
    RoomMonitorOption,
)
from app.services.dashboard import DashboardService

router = APIRouter(prefix="/dashboard")


@router.get("/summary", response_model=ApiResponse[DashboardSummary])
async def dashboard_summary(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[User, Depends(require_permissions("dashboard:view"))],
) -> ApiResponse[DashboardSummary]:
    data = await service.get_summary()
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/utilization", response_model=ApiResponse[DashboardUtilization])
async def dashboard_utilization(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[User, Depends(require_permissions("dashboard:view"))],
) -> ApiResponse[DashboardUtilization]:
    data = await service.get_utilization()
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/analytics", response_model=ApiResponse[DashboardAnalytics])
async def dashboard_analytics(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[User, Depends(require_permissions("dashboard:view"))],
) -> ApiResponse[DashboardAnalytics]:
    data = await service.get_analytics()
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/rooms", response_model=ApiResponse[list[RoomMonitorOption]])
async def dashboard_rooms(
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[User, Depends(require_permissions("dashboard:view"))],
) -> ApiResponse[list[RoomMonitorOption]]:
    data = await service.list_room_monitor_options()
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/rooms/{room_id}/layout", response_model=ApiResponse[RoomMonitorLayout])
async def dashboard_room_layout(
    room_id: uuid.UUID,
    service: Annotated[DashboardService, Depends(get_dashboard_service)],
    _: Annotated[User, Depends(require_permissions("dashboard:view"))],
) -> ApiResponse[RoomMonitorLayout]:
    data = await service.get_room_monitor_layout(room_id)
    return ApiResponse(data=data, timestamp=datetime.now())
