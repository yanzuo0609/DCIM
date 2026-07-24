import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_network_design_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.network import (
    NetworkProjectCreate,
    NetworkProjectResponse,
    NetworkProjectUpdate,
)
from app.services.network import NetworkDesignService

router = APIRouter(prefix="/network-projects")


@router.get("", response_model=PaginatedResponse[NetworkProjectResponse])
async def list_projects(
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = None,
    sort: str = "updated_at",
    order: str = "desc",
) -> PaginatedResponse[NetworkProjectResponse]:
    params = PaginationParams(
        page=page, page_size=page_size, keyword=keyword, sort=sort, order=order
    )
    items, pagination = await service.list_projects(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("", response_model=ApiResponse[NetworkProjectResponse], status_code=201)
async def create_project(
    payload: NetworkProjectCreate,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:create"))],
) -> ApiResponse[NetworkProjectResponse]:
    data = await service.create_project(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/{project_id}", response_model=ApiResponse[NetworkProjectResponse])
async def get_project(
    project_id: uuid.UUID,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    _: Annotated[User, Depends(require_permissions("network:view"))],
) -> ApiResponse[NetworkProjectResponse]:
    data = await service.get_project(project_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{project_id}", response_model=ApiResponse[NetworkProjectResponse])
async def update_project(
    project_id: uuid.UUID,
    payload: NetworkProjectUpdate,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:update"))],
) -> ApiResponse[NetworkProjectResponse]:
    data = await service.update_project(project_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{project_id}", response_model=ApiResponse[dict[str, str]])
async def delete_project(
    project_id: uuid.UUID,
    service: Annotated[NetworkDesignService, Depends(get_network_design_service)],
    current_user: Annotated[User, Depends(require_permissions("network:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_project(project_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
