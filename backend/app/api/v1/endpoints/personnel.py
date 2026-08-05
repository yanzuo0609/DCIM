"""Personnel management API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.core.dependencies import get_personnel_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.personnel import (
    InternalCreate,
    InternalResponse,
    InternalUpdate,
    OrgChartBrief,
    OrgChartCreate,
    OrgChartResponse,
    OrgChartUpdate,
    SupplierCreate,
    SupplierResponse,
    SupplierUpdate,
)
from app.services.personnel import PersonnelService

router = APIRouter(prefix="/personnel", tags=["personnel"])


@router.get("/org-charts", response_model=ApiResponse[list[OrgChartBrief]])
async def list_org_charts(
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    project_no: str | None = None,
) -> ApiResponse[list[OrgChartBrief]]:
    data = await service.list_org_charts(project_no)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/org-charts", response_model=ApiResponse[OrgChartResponse], status_code=201)
async def create_org_chart(
    payload: OrgChartCreate,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:create"))],
) -> ApiResponse[OrgChartResponse]:
    data = await service.create_org_chart(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/org-charts/{chart_id}", response_model=ApiResponse[OrgChartResponse])
async def get_org_chart(
    chart_id: uuid.UUID,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
) -> ApiResponse[OrgChartResponse]:
    data = await service.get_org_chart(chart_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/org-charts/{chart_id}", response_model=ApiResponse[OrgChartResponse])
async def update_org_chart(
    chart_id: uuid.UUID,
    payload: OrgChartUpdate,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[OrgChartResponse]:
    data = await service.update_org_chart(chart_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/org-charts/{chart_id}", response_model=ApiResponse[dict[str, str]])
async def delete_org_chart(
    chart_id: uuid.UUID,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_org_chart(chart_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.get("/internals", response_model=PaginatedResponse[InternalResponse])
async def list_internals(
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[InternalResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_internals(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("/internals", response_model=ApiResponse[InternalResponse], status_code=201)
async def create_internal(
    payload: InternalCreate,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:create"))],
) -> ApiResponse[InternalResponse]:
    data = await service.create_internal(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/internals/{internal_id}", response_model=ApiResponse[InternalResponse])
async def update_internal(
    internal_id: uuid.UUID,
    payload: InternalUpdate,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[InternalResponse]:
    data = await service.update_internal(internal_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/internals/{internal_id}", response_model=ApiResponse[dict[str, str]])
async def delete_internal(
    internal_id: uuid.UUID,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_internal(internal_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.get("/suppliers", response_model=PaginatedResponse[SupplierResponse])
async def list_suppliers(
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
    manufacturer_id: str | None = None,
) -> PaginatedResponse[SupplierResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    mfg_uuid = None
    if manufacturer_id:
        mfg_uuid = uuid.UUID(manufacturer_id)
    items, pagination = await service.list_suppliers(params, manufacturer_id=mfg_uuid)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("/suppliers", response_model=ApiResponse[SupplierResponse], status_code=201)
async def create_supplier(
    payload: SupplierCreate,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:create"))],
) -> ApiResponse[SupplierResponse]:
    data = await service.create_supplier(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/suppliers/{supplier_id}", response_model=ApiResponse[SupplierResponse])
async def update_supplier(
    supplier_id: uuid.UUID,
    payload: SupplierUpdate,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[SupplierResponse]:
    data = await service.update_supplier(supplier_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/suppliers/{supplier_id}", response_model=ApiResponse[dict[str, str]])
async def delete_supplier(
    supplier_id: uuid.UUID,
    service: Annotated[PersonnelService, Depends(get_personnel_service)],
    current_user: Annotated[User, Depends(require_permissions("device:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_supplier(supplier_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
