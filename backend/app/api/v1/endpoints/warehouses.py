import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_warehouse_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.infrastructure import (
    WarehouseAssetCreate,
    WarehouseAssetResponse,
    WarehouseAssetUpdate,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)
from app.services.warehouse import WarehouseService

router = APIRouter(prefix="/warehouses")


@router.get("", response_model=PaginatedResponse[WarehouseResponse])
async def list_warehouses(
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    _: Annotated[User, Depends(require_permissions("datacenter:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = None,
    room_id: uuid.UUID | None = None,
    datacenter_id: uuid.UUID | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> PaginatedResponse[WarehouseResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword, sort=sort, order=order)
    items, pagination = await service.list(
        params, room_id=room_id, datacenter_id=datacenter_id
    )
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("", response_model=ApiResponse[WarehouseResponse], status_code=201)
async def create_warehouse(
    payload: WarehouseCreate,
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:create"))],
) -> ApiResponse[WarehouseResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/{warehouse_id}", response_model=ApiResponse[WarehouseResponse])
async def get_warehouse(
    warehouse_id: uuid.UUID,
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    _: Annotated[User, Depends(require_permissions("datacenter:view"))],
) -> ApiResponse[WarehouseResponse]:
    data = await service.get(warehouse_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{warehouse_id}", response_model=ApiResponse[WarehouseResponse])
async def update_warehouse(
    warehouse_id: uuid.UUID,
    payload: WarehouseUpdate,
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:update"))],
) -> ApiResponse[WarehouseResponse]:
    data = await service.update(warehouse_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{warehouse_id}", response_model=ApiResponse[dict], status_code=200)
async def delete_warehouse(
    warehouse_id: uuid.UUID,
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:delete"))],
) -> ApiResponse[dict]:
    await service.delete(warehouse_id, user_id=current_user.id)
    return ApiResponse(data={"id": str(warehouse_id)}, timestamp=datetime.now())


@router.get("/{warehouse_id}/assets", response_model=PaginatedResponse[WarehouseAssetResponse])
async def list_warehouse_assets(
    warehouse_id: uuid.UUID,
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    _: Annotated[User, Depends(require_permissions("datacenter:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    keyword: str | None = None,
    sort: str = "created_at",
    order: str = "desc",
) -> PaginatedResponse[WarehouseAssetResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword, sort=sort, order=order)
    items, pagination = await service.list_assets(warehouse_id, params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post(
    "/{warehouse_id}/assets",
    response_model=ApiResponse[WarehouseAssetResponse],
    status_code=201,
)
async def create_warehouse_asset(
    warehouse_id: uuid.UUID,
    payload: WarehouseAssetCreate,
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:create"))],
) -> ApiResponse[WarehouseAssetResponse]:
    data = await service.create_asset(warehouse_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put(
    "/{warehouse_id}/assets/{asset_id}",
    response_model=ApiResponse[WarehouseAssetResponse],
)
async def update_warehouse_asset(
    warehouse_id: uuid.UUID,
    asset_id: uuid.UUID,
    payload: WarehouseAssetUpdate,
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:update"))],
) -> ApiResponse[WarehouseAssetResponse]:
    data = await service.update_asset(
        warehouse_id, asset_id, payload, user_id=current_user.id
    )
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete(
    "/{warehouse_id}/assets/{asset_id}",
    response_model=ApiResponse[dict],
    status_code=200,
)
async def delete_warehouse_asset(
    warehouse_id: uuid.UUID,
    asset_id: uuid.UUID,
    service: Annotated[WarehouseService, Depends(get_warehouse_service)],
    current_user: Annotated[User, Depends(require_permissions("datacenter:delete"))],
) -> ApiResponse[dict]:
    await service.delete_asset(warehouse_id, asset_id, user_id=current_user.id)
    return ApiResponse(data={"id": str(asset_id)}, timestamp=datetime.now())
