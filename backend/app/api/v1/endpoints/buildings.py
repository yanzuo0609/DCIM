import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_building_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.infrastructure import BuildingCreate, BuildingResponse, BuildingUpdate
from app.services.infrastructure import BuildingService

router = APIRouter(prefix="/buildings")


@router.get("", response_model=PaginatedResponse[BuildingResponse])
async def list_buildings(
    service: Annotated[BuildingService, Depends(get_building_service)],
    _: Annotated[User, Depends(require_permissions("datacenter:view"))],
    datacenter_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[BuildingResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list(params, datacenter_id=datacenter_id)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("", response_model=ApiResponse[BuildingResponse], status_code=201)
async def create_building(
    payload: BuildingCreate,
    service: Annotated[BuildingService, Depends(get_building_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:create"))],
) -> ApiResponse[BuildingResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{building_id}", response_model=ApiResponse[BuildingResponse])
async def update_building(
    building_id: uuid.UUID,
    payload: BuildingUpdate,
    service: Annotated[BuildingService, Depends(get_building_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:update"))],
) -> ApiResponse[BuildingResponse]:
    data = await service.update(building_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{building_id}", response_model=ApiResponse[dict[str, str]])
async def delete_building(
    building_id: uuid.UUID,
    service: Annotated[BuildingService, Depends(get_building_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete(building_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
