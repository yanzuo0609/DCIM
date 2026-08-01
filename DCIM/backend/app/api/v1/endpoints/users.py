import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_role_mgmt_service, get_user_mgmt_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.user_mgmt import (
    PermissionResponse,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)
from app.services.user_mgmt import RoleManagementService, UserManagementService

router = APIRouter()


@router.get("/users", response_model=PaginatedResponse[UserResponse])
async def list_users(
    service: Annotated[UserManagementService, Depends(get_user_mgmt_service)],
    _: Annotated[User, Depends(require_permissions("user:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[UserResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_users(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.get("/users/{user_id}", response_model=ApiResponse[UserResponse])
async def get_user(
    user_id: uuid.UUID,
    service: Annotated[UserManagementService, Depends(get_user_mgmt_service)],
    _: Annotated[User, Depends(require_permissions("user:view"))],
) -> ApiResponse[UserResponse]:
    data = await service.get_user(user_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/users", response_model=ApiResponse[UserResponse], status_code=201)
async def create_user(
    payload: UserCreate,
    service: Annotated[UserManagementService, Depends(get_user_mgmt_service)],
    current_user: Annotated[User, Depends(require_permissions("user:create"))],
) -> ApiResponse[UserResponse]:
    data = await service.create_user(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/users/{user_id}", response_model=ApiResponse[UserResponse])
async def update_user(
    user_id: uuid.UUID,
    payload: UserUpdate,
    service: Annotated[UserManagementService, Depends(get_user_mgmt_service)],
    current_user: Annotated[User, Depends(require_permissions("user:update"))],
) -> ApiResponse[UserResponse]:
    data = await service.update_user(user_id, payload, actor_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/users/{user_id}", response_model=ApiResponse[dict[str, str]])
async def delete_user(
    user_id: uuid.UUID,
    service: Annotated[UserManagementService, Depends(get_user_mgmt_service)],
    current_user: Annotated[User, Depends(require_permissions("user:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_user(user_id, actor_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.get("/roles", response_model=PaginatedResponse[RoleResponse])
async def list_roles(
    service: Annotated[RoleManagementService, Depends(get_role_mgmt_service)],
    _: Annotated[User, Depends(require_permissions("role:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[RoleResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_roles(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("/roles", response_model=ApiResponse[RoleResponse], status_code=201)
async def create_role(
    payload: RoleCreate,
    service: Annotated[RoleManagementService, Depends(get_role_mgmt_service)],
    current_user: Annotated[User, Depends(require_permissions("role:create"))],
) -> ApiResponse[RoleResponse]:
    data = await service.create_role(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/roles/{role_id}", response_model=ApiResponse[RoleResponse])
async def update_role(
    role_id: uuid.UUID,
    payload: RoleUpdate,
    service: Annotated[RoleManagementService, Depends(get_role_mgmt_service)],
    current_user: Annotated[User, Depends(require_permissions("role:update"))],
) -> ApiResponse[RoleResponse]:
    data = await service.update_role(role_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/roles/{role_id}", response_model=ApiResponse[dict[str, str]])
async def delete_role(
    role_id: uuid.UUID,
    service: Annotated[RoleManagementService, Depends(get_role_mgmt_service)],
    current_user: Annotated[User, Depends(require_permissions("role:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_role(role_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.get("/permissions", response_model=ApiResponse[list[PermissionResponse]])
async def list_permissions(
    service: Annotated[RoleManagementService, Depends(get_role_mgmt_service)],
    _: Annotated[User, Depends(require_permissions("role:view"))],
) -> ApiResponse[list[PermissionResponse]]:
    data = await service.list_permissions()
    return ApiResponse(data=data, timestamp=datetime.now())
