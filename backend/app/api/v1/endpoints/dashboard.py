from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_dashboard_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.dashboard import DashboardSummary, DashboardUtilization
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
