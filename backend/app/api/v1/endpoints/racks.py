import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.dependencies import get_layout_service, get_rack_service, get_svg_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.layout import RackMountBody, ValidateLayoutResponse
from app.schemas.rack import (
    PlaceBatchRequest,
    PlaceBatchResult,
    RackBatchDeleteRequest,
    RackBatchDeleteResult,
    RackCodeCheckResponse,
    RackCreate,
    RackLayoutResponse,
    RackResponse,
    RackUpdate,
)
from app.services.layout import LayoutService
from app.services.rack import RackService
from app.services.svg import SVGService

router = APIRouter(prefix="/racks")


@router.get("", response_model=PaginatedResponse[RackResponse])
async def list_racks(
    service: Annotated[RackService, Depends(get_rack_service)],
    _: Annotated[User, Depends(require_permissions("rack:view"))],
    room_id: uuid.UUID | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=500),
    keyword: str | None = None,
    sort: str = "code",
    order: str = "asc",
) -> PaginatedResponse[RackResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword, sort=sort, order=order)
    items, pagination = await service.list(params, room_id=room_id)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.get("/code-check", response_model=ApiResponse[RackCodeCheckResponse])
async def check_rack_code(
    service: Annotated[RackService, Depends(get_rack_service)],
    _: Annotated[User, Depends(require_permissions("rack:view"))],
    code: str = Query(min_length=1, max_length=50),
    room_id: uuid.UUID | None = None,
    preferred_base: str | None = None,
) -> ApiResponse[RackCodeCheckResponse]:
    data = await service.check_code(code, room_id=room_id, preferred_base=preferred_base)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/place-batch", response_model=ApiResponse[PlaceBatchResult])
async def place_racks_batch(
    payload: PlaceBatchRequest,
    service: Annotated[RackService, Depends(get_rack_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:create"))],
) -> ApiResponse[PlaceBatchResult]:
    data = await service.place_batch(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/batch-delete", response_model=ApiResponse[RackBatchDeleteResult])
async def batch_delete_racks(
    payload: RackBatchDeleteRequest,
    service: Annotated[RackService, Depends(get_rack_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:delete"))],
) -> ApiResponse[RackBatchDeleteResult]:
    data = await service.batch_delete(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/{rack_id}", response_model=ApiResponse[RackResponse])
async def get_rack(
    rack_id: uuid.UUID,
    service: Annotated[RackService, Depends(get_rack_service)],
    _: Annotated[User, Depends(require_permissions("rack:view"))],
) -> ApiResponse[RackResponse]:
    data = await service.get(rack_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/{rack_id}/layout", response_model=ApiResponse[RackLayoutResponse])
async def get_rack_layout(
    rack_id: uuid.UUID,
    service: Annotated[RackService, Depends(get_rack_service)],
    _: Annotated[User, Depends(require_permissions("rack:view"))],
) -> ApiResponse[RackLayoutResponse]:
    data = await service.get_layout(rack_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/{rack_id}/svg")
async def get_rack_svg(
    rack_id: uuid.UUID,
    service: Annotated[SVGService, Depends(get_svg_service)],
    _: Annotated[User, Depends(require_permissions("rack:view"))],
) -> Response:
    svg = await service.render_rack(rack_id)
    return Response(content=svg, media_type="image/svg+xml")


@router.post("/{rack_id}/layout", response_model=ApiResponse[ValidateLayoutResponse])
async def mount_rack_layout(
    rack_id: uuid.UUID,
    payload: RackMountBody,
    service: Annotated[LayoutService, Depends(get_layout_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[ValidateLayoutResponse]:
    from app.schemas.layout import MountRequest

    data = await service.mount(
        MountRequest(
            device_id=payload.device_id,
            rack_id=str(rack_id),
            u_position=payload.u_position,
        ),
        user_id=current_user.id,
    )
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("", response_model=ApiResponse[RackResponse], status_code=201)
async def create_rack(
    payload: RackCreate,
    service: Annotated[RackService, Depends(get_rack_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:create"))],
) -> ApiResponse[RackResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{rack_id}", response_model=ApiResponse[RackResponse])
async def update_rack(
    rack_id: uuid.UUID,
    payload: RackUpdate,
    service: Annotated[RackService, Depends(get_rack_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:update"))],
) -> ApiResponse[RackResponse]:
    data = await service.update(rack_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{rack_id}", response_model=ApiResponse[dict[str, str]])
async def delete_rack(
    rack_id: uuid.UUID,
    service: Annotated[RackService, Depends(get_rack_service)],
    current_user: Annotated[User, Depends(require_permissions("rack:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete(rack_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
