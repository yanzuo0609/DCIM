import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_floor_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.infrastructure import FloorCreate, FloorResponse, FloorUpdate
from app.services.infrastructure import FloorService

router = APIRouter(prefix="/floors")


@router.get("", response_model=PaginatedResponse[FloorResponse])
async def list_floors(
    service: Annotated[FloorService, Depends(get_floor_service)],
    _: Annotated[User, Depends(require_permissions("datacenter:view"))],
    building_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[FloorResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list(params, building_id=building_id)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("", response_model=ApiResponse[FloorResponse], status_code=201)
async def create_floor(
    payload: FloorCreate,
    service: Annotated[FloorService, Depends(get_floor_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:create"))],
) -> ApiResponse[FloorResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{floor_id}", response_model=ApiResponse[FloorResponse])
async def update_floor(
    floor_id: uuid.UUID,
    payload: FloorUpdate,
    service: Annotated[FloorService, Depends(get_floor_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:update"))],
) -> ApiResponse[FloorResponse]:
    data = await service.update(floor_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{floor_id}", response_model=ApiResponse[dict[str, str]])
async def delete_floor(
    floor_id: uuid.UUID,
    service: Annotated[FloorService, Depends(get_floor_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete(floor_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
