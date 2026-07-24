import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_network_design_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.network import (
    CanvasSaveRequest,
    NetworkTopologyCreate,
    NetworkTopologyDetailResponse,
    NetworkTopologyResponse,
    NetworkTopologyUpdate,
)
from app.services.network import NetworkDesignService

router = APIRouter(prefix="/network-topologies")


@router.get("", response_model=PaginatedResponse[NetworkTopologyResponse])
async def list_topologies(
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
) -> PaginatedResponse[NetworkTopologyResponse]:
    params = PaginationParams(
        page=page, page_size=page_size, keyword=keyword, sort=sort, order=order
    )
    items, pagination = await service.list_topologies(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("", response_model=ApiResponse[NetworkTopologyResponse], status_code=201)
async def create_topology(
    payload: NetworkTopologyCreate,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:create"))],
) -> ApiResponse[NetworkTopologyResponse]:
    data = await service.create_topology(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/{topology_id}", response_model=ApiResponse[NetworkTopologyDetailResponse])
async def get_topology_detail(
    topology_id: uuid.UUID,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[NetworkTopologyDetailResponse]:
    data = await service.get_detail(topology_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{topology_id}", response_model=ApiResponse[NetworkTopologyResponse])
async def update_topology(
    topology_id: uuid.UUID,
    payload: NetworkTopologyUpdate,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkTopologyResponse]:
    data = await service.update_topology(topology_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{topology_id}/canvas", response_model=ApiResponse[NetworkTopologyDetailResponse])
async def save_topology_canvas(
    topology_id: uuid.UUID,
    payload: CanvasSaveRequest,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkTopologyDetailResponse]:
    data = await service.save_canvas(topology_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{topology_id}", response_model=ApiResponse[dict[str, str]])
async def delete_topology(
    topology_id: uuid.UUID,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_topology(topology_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
