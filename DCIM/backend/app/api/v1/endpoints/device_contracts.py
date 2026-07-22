import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from app.core.dependencies import get_device_contract_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.device_contract import (
    DeviceContractBindRequest,
    DeviceContractBindResult,
    DeviceContractCreate,
    DeviceContractItemsImportResult,
    DeviceContractResponse,
    DeviceContractSummaryItem,
    DeviceContractUpdate,
)
from app.services.contract_export import ContractItemsExportService
from app.services.device_contract import DeviceContractService

router = APIRouter(prefix="/device-contracts")
items_export_service = ContractItemsExportService()


@router.get("/items/import/template")
async def download_contract_items_template(
    _: Annotated[User, Depends(require_permissions("device:view"))],
) -> Response:
    content = items_export_service.template_excel()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": 'attachment; filename="contract_items_template.xlsx"'
        },
    )


@router.post(
    "/items/import",
    response_model=ApiResponse[DeviceContractItemsImportResult],
)
async def import_contract_items(
    _: Annotated[User, Depends(require_permissions("device:create"))],
    file: UploadFile = File(...),
) -> ApiResponse[DeviceContractItemsImportResult]:
    content = await file.read()
    items, errors = items_export_service.parse_excel(content)
    return ApiResponse(
        data=DeviceContractItemsImportResult(
            items=items,
            imported=len(items),
            skipped=len(errors),
            errors=errors,
        ),
        timestamp=datetime.now(),
    )


@router.get("/summary", response_model=ApiResponse[list[DeviceContractSummaryItem]])
async def contract_summary(
    service: Annotated[DeviceContractService, Depends(get_device_contract_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
) -> ApiResponse[list[DeviceContractSummaryItem]]:
    data = await service.summary()
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("", response_model=PaginatedResponse[DeviceContractResponse])
async def list_contracts(
    service: Annotated[DeviceContractService, Depends(get_device_contract_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = None,
    sort: str = "purchase_date",
    order: str = "desc",
) -> PaginatedResponse[DeviceContractResponse]:
    params = PaginationParams(
        page=page, page_size=page_size, keyword=keyword, sort=sort, order=order
    )
    items, pagination = await service.list(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.get("/{contract_id}", response_model=ApiResponse[DeviceContractResponse])
async def get_contract(
    contract_id: uuid.UUID,
    service: Annotated[DeviceContractService, Depends(get_device_contract_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
) -> ApiResponse[DeviceContractResponse]:
    data = await service.get(contract_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("", response_model=ApiResponse[DeviceContractResponse], status_code=201)
async def create_contract(
    payload: DeviceContractCreate,
    service: Annotated[DeviceContractService, Depends(get_device_contract_service)],
    current_user: Annotated[User, Depends(require_permissions("device:create"))],
) -> ApiResponse[DeviceContractResponse]:
    data = await service.create(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/{contract_id}", response_model=ApiResponse[DeviceContractResponse])
async def update_contract(
    contract_id: uuid.UUID,
    payload: DeviceContractUpdate,
    service: Annotated[DeviceContractService, Depends(get_device_contract_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[DeviceContractResponse]:
    data = await service.update(contract_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/{contract_id}", response_model=ApiResponse[dict[str, str]])
async def delete_contract(
    contract_id: uuid.UUID,
    service: Annotated[DeviceContractService, Depends(get_device_contract_service)],
    current_user: Annotated[User, Depends(require_permissions("device:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete(contract_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.post(
    "/{contract_id}/bind-devices",
    response_model=ApiResponse[DeviceContractBindResult],
)
async def bind_devices(
    contract_id: uuid.UUID,
    payload: DeviceContractBindRequest,
    service: Annotated[DeviceContractService, Depends(get_device_contract_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[DeviceContractBindResult]:
    data = await service.bind_devices(contract_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post(
    "/{contract_id}/unbind-devices",
    response_model=ApiResponse[DeviceContractBindResult],
)
async def unbind_devices(
    contract_id: uuid.UUID,
    payload: DeviceContractBindRequest,
    service: Annotated[DeviceContractService, Depends(get_device_contract_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[DeviceContractBindResult]:
    data = await service.unbind_devices(contract_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())
