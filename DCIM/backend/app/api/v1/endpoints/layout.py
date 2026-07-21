from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_layout_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse
from app.schemas.device import (
    BatchMountRequest,
    BatchMountResult,
    BatchUnmountRequest,
    BatchUnmountResult,
)
from app.schemas.layout import (
    AutoLayoutRequest,
    AutoLayoutResponse,
    MountRequest,
    UnmountRequest,
    ValidateLayoutRequest,
    ValidateLayoutResponse,
)
from app.services.layout import LayoutService

router = APIRouter(prefix="/layout")


@router.post("/validate", response_model=ApiResponse[ValidateLayoutResponse])
async def validate_layout(
    payload: ValidateLayoutRequest,
    service: Annotated[LayoutService, Depends(get_layout_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
) -> ApiResponse[ValidateLayoutResponse]:
    data = await service.validate(payload)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/auto", response_model=ApiResponse[AutoLayoutResponse])
async def auto_layout(
    payload: AutoLayoutRequest,
    service: Annotated[LayoutService, Depends(get_layout_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[AutoLayoutResponse]:
    data = await service.auto_layout(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/mount", response_model=ApiResponse[ValidateLayoutResponse])
async def mount_device(
    payload: MountRequest,
    service: Annotated[LayoutService, Depends(get_layout_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[ValidateLayoutResponse]:
    data = await service.mount(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/unmount", response_model=ApiResponse[ValidateLayoutResponse])
async def unmount_device(
    payload: UnmountRequest,
    service: Annotated[LayoutService, Depends(get_layout_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[ValidateLayoutResponse]:
    data = await service.unmount(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/batch-mount", response_model=ApiResponse[BatchMountResult])
async def batch_mount_devices(
    payload: BatchMountRequest,
    service: Annotated[LayoutService, Depends(get_layout_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[BatchMountResult]:
    data = await service.batch_mount(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/batch-unmount", response_model=ApiResponse[BatchUnmountResult])
async def batch_unmount_devices(
    payload: BatchUnmountRequest,
    service: Annotated[LayoutService, Depends(get_layout_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[BatchUnmountResult]:
    data = await service.batch_unmount(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())
