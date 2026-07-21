import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_rack_template_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.rack import (
    ApplyTemplateToRoomRequest,
    ApplyTemplateToRoomResult,
    RackTemplateCreate,
    RackTemplateResponse,
    RackTemplateUpdate,
    UnapplyTemplateFromRoomRequest,
    UnapplyTemplateFromRoomResult,
)
from app.services.rack import RackTemplateService

router = APIRouter(prefix="/rack-templates")


@router.get("", response_model=PaginatedResponse[RackTemplateResponse])
async def list_rack_templates(
    service: Annotated[RackTemplateService, Depends(get_rack_template_service)],
    _: Annotated[User, Depends(require_permissions("rack:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[RackTemplateResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("", response_model=ApiResponse[RackTemplateResponse], status_code=201)
async def create_rack_template(
    payload: RackTemplateCreate,
    service: Annotated[RackTemplateService, Depends(get_rack_template_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:create"))],
) -> ApiResponse[RackTemplateResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post(
    "/{template_id}/apply-to-room",
    response_model=ApiResponse[ApplyTemplateToRoomResult],
)
async def apply_rack_template_to_room(
    template_id: uuid.UUID,
    payload: ApplyTemplateToRoomRequest,
    service: Annotated[RackTemplateService, Depends(get_rack_template_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:update"))],
) -> ApiResponse[ApplyTemplateToRoomResult]:
    data = await service.apply_to_room(template_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post(
    "/{template_id}/unapply-from-room",
    response_model=ApiResponse[UnapplyTemplateFromRoomResult],
)
async def unapply_rack_template_from_room(
    template_id: uuid.UUID,
    payload: UnapplyTemplateFromRoomRequest,
    service: Annotated[RackTemplateService, Depends(get_rack_template_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:update"))],
) -> ApiResponse[UnapplyTemplateFromRoomResult]:
    data = await service.unapply_from_room(template_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{template_id}", response_model=ApiResponse[RackTemplateResponse])
async def update_rack_template(
    template_id: uuid.UUID,
    payload: RackTemplateUpdate,
    service: Annotated[RackTemplateService, Depends(get_rack_template_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:update"))],
) -> ApiResponse[RackTemplateResponse]:
    data = await service.update(template_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{template_id}", response_model=ApiResponse[dict[str, str]])
async def delete_rack_template(
    template_id: uuid.UUID,
    service: Annotated[RackTemplateService, Depends(get_rack_template_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete(template_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
