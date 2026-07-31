import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_ip_address_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.ip_address import (
    IpAddressBatchCreateRequest,
    IpAddressBatchCreateResult,
    IpAddressCreate,
    IpAddressResponse,
    IpAddressUpdate,
    IpAllocateRequest,
    IpAllocateResult,
    IpBatchDeleteRequest,
    IpBatchDeleteResult,
    IpBindBatchRequest,
    IpBindBatchResult,
    IpBindRequest,
    IpSegmentCreate,
    IpSegmentDetail,
    IpSegmentResponse,
    IpSegmentUpdate,
    IpStatusBatchRequest,
    IpStatusBatchResult,
)
from app.services.ip_address import IpAddressService

router = APIRouter(prefix="/ip-addresses", tags=["ip-addresses"])


@router.get("/segments", response_model=PaginatedResponse[IpSegmentResponse])
async def list_ip_segments(
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    keyword: str | None = None,
    application_type: str | None = None,
) -> PaginatedResponse[IpSegmentResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_segments(
        params, application_type=application_type
    )
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("/segments", response_model=ApiResponse[IpSegmentDetail], status_code=201)
async def create_ip_segment(
    payload: IpSegmentCreate,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpSegmentDetail]:
    data = await service.create_segment(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/segments/{segment_id}", response_model=ApiResponse[IpSegmentDetail])
async def get_ip_segment(
    segment_id: uuid.UUID,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
) -> ApiResponse[IpSegmentDetail]:
    data = await service.get_segment(segment_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/segments/{segment_id}", response_model=ApiResponse[IpSegmentDetail])
async def update_ip_segment(
    segment_id: uuid.UUID,
    payload: IpSegmentUpdate,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpSegmentDetail]:
    data = await service.update_segment(segment_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/segments/{segment_id}", response_model=ApiResponse[dict[str, str]])
async def delete_ip_segment(
    segment_id: uuid.UUID,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_segment(segment_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.get("", response_model=PaginatedResponse[IpAddressResponse])
async def list_ip_addresses(
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    keyword: str | None = None,
    room_id: uuid.UUID | None = None,
    rack_id: uuid.UUID | None = None,
    device_id: uuid.UUID | None = None,
    bind_type: str | None = None,
    status: str | None = None,
) -> PaginatedResponse[IpAddressResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_ips(
        params,
        room_id=room_id,
        rack_id=rack_id,
        device_id=device_id,
        bind_type=bind_type,
        status=status,
    )
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("", response_model=ApiResponse[IpAddressResponse], status_code=201)
async def create_ip_address(
    payload: IpAddressCreate,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpAddressResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/batch-create", response_model=ApiResponse[IpAddressBatchCreateResult])
async def batch_create_ip_addresses(
    payload: IpAddressBatchCreateRequest,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpAddressBatchCreateResult]:
    data = await service.batch_create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/batch-delete", response_model=ApiResponse[IpBatchDeleteResult])
async def batch_delete_ip_addresses(
    payload: IpBatchDeleteRequest,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpBatchDeleteResult]:
    data = await service.batch_delete(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/batch-bind", response_model=ApiResponse[IpBindBatchResult])
async def batch_bind_ip_addresses(
    payload: IpBindBatchRequest,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpBindBatchResult]:
    data = await service.bind_batch(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/allocate", response_model=ApiResponse[IpAllocateResult])
async def allocate_ip_addresses(
    payload: IpAllocateRequest,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpAllocateResult]:
    data = await service.allocate(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/batch-status", response_model=ApiResponse[IpStatusBatchResult])
async def batch_set_ip_status(
    payload: IpStatusBatchRequest,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpStatusBatchResult]:
    data = await service.set_status_batch(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{ip_id}", response_model=ApiResponse[IpAddressResponse])
async def update_ip_address(
    ip_id: uuid.UUID,
    payload: IpAddressUpdate,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpAddressResponse]:
    data = await service.update(ip_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/{ip_id}/bind", response_model=ApiResponse[IpAddressResponse])
async def bind_ip_address(
    ip_id: uuid.UUID,
    payload: IpBindRequest,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[IpAddressResponse]:
    data = await service.bind_one(ip_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{ip_id}", response_model=ApiResponse[dict[str, str]])
async def delete_ip_address(
    ip_id: uuid.UUID,
    service: Annotated[IpAddressService, Depends(get_ip_address_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete(ip_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
