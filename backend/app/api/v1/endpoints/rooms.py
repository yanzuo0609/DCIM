import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_room_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.infrastructure import RoomCreate, RoomQuickCreate, RoomResponse, RoomUpdate
from app.services.infrastructure import RoomService

router = APIRouter(prefix="/rooms")


@router.get("", response_model=PaginatedResponse[RoomResponse])
async def list_rooms(
    service: Annotated[RoomService, Depends(get_room_service)],
    _: Annotated[User, Depends(require_permissions("datacenter:view"))],
    floor_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    keyword: str | None = None,
) -> PaginatedResponse[RoomResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list(params, floor_id=floor_id)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("", response_model=ApiResponse[RoomResponse], status_code=201)
async def create_room(
    payload: RoomCreate,
    service: Annotated[RoomService, Depends(get_room_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:create"))],
) -> ApiResponse[RoomResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/quick", response_model=ApiResponse[RoomResponse], status_code=201)
async def create_room_quick(
    payload: RoomQuickCreate,
    service: Annotated[RoomService, Depends(get_room_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:create"))],
) -> ApiResponse[RoomResponse]:
    data = await service.create_quick(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{room_id}", response_model=ApiResponse[RoomResponse])
async def update_room(
    room_id: uuid.UUID,
    payload: RoomUpdate,
    service: Annotated[RoomService, Depends(get_room_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:update"))],
) -> ApiResponse[RoomResponse]:
    data = await service.update(room_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{room_id}", response_model=ApiResponse[dict[str, str]])
async def delete_room(
    room_id: uuid.UUID,
    service: Annotated[RoomService, Depends(get_room_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete(room_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
