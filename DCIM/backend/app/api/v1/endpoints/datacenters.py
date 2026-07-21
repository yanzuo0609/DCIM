import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_current_user, get_datacenter_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.infrastructure import (
    DataCenterCreate,
    DataCenterResponse,
    DataCenterUpdate,
)
from app.services.infrastructure import DataCenterService

router = APIRouter(prefix="/datacenters")


@router.get("", response_model=PaginatedResponse[DataCenterResponse])
async def list_datacenters(
    service: Annotated[DataCenterService, Depends(get_datacenter_service)],
    _: Annotated[User, Depends(require_permissions("datacenter:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> PaginatedResponse[DataCenterResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword, sort=sort, order=order)
    items, pagination = await service.list(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.get("/{datacenter_id}", response_model=ApiResponse[DataCenterResponse])
async def get_datacenter(
    datacenter_id: uuid.UUID,
    service: Annotated[DataCenterService, Depends(get_datacenter_service)],
    _: Annotated[User, Depends(require_permissions("datacenter:view"))],
) -> ApiResponse[DataCenterResponse]:
    data = await service.get(datacenter_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("", response_model=ApiResponse[DataCenterResponse], status_code=201)
async def create_datacenter(
    payload: DataCenterCreate,
    service: Annotated[DataCenterService, Depends(get_datacenter_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:create"))],
) -> ApiResponse[DataCenterResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{datacenter_id}", response_model=ApiResponse[DataCenterResponse])
async def update_datacenter(
    datacenter_id: uuid.UUID,
    payload: DataCenterUpdate,
    service: Annotated[DataCenterService, Depends(get_datacenter_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:update"))],
) -> ApiResponse[DataCenterResponse]:
    data = await service.update(datacenter_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{datacenter_id}", response_model=ApiResponse[dict[str, str]])
async def delete_datacenter(
    datacenter_id: uuid.UUID,
    service: Annotated[DataCenterService, Depends(get_datacenter_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete(datacenter_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
