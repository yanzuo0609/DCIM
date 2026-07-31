import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import Response

from app.core.dependencies import get_device_export_service, get_device_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.schemas.device import (
    DeviceBatchDeleteRequest,
    DeviceBatchDeleteResult,
    DeviceCreate,
    DeviceModelCreate,
    DeviceModelResponse,
    DeviceModelUpdate,
    DeviceResponse,
    DeviceTypeCreate,
    DeviceTypeResponse,
    DeviceTypeUpdate,
    DeviceUpdate,
    ManufacturerCreate,
    ManufacturerResponse,
    BmcProfileCreate,
    BmcProfileResponse,
    BmcProfileUpdate,
    ParamProfileCreate,
    ParamProfileResponse,
    ParamProfileUpdate,
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
    SystemProfileCreate,
    SystemProfileResponse,
    SystemProfileUpdate,
)
from app.schemas.export import ImportResult
from app.services.device import DeviceService
from app.services.export import DeviceExportService

router = APIRouter()


@router.get("/devices", response_model=PaginatedResponse[DeviceResponse])
async def list_devices(
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    rack_id: uuid.UUID | None = None,
    room_id: uuid.UUID | None = None,
    status: str | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    keyword: str | None = None,
) -> PaginatedResponse[DeviceResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_devices(
        params, rack_id=rack_id, room_id=room_id, status=status
    )
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.get("/devices/export")
async def export_devices(
    export_service: Annotated[DeviceExportService, Depends(get_device_export_service)],
    _: Annotated[User, Depends(require_permissions("device:export"))],
    format: str = Query(default="xlsx", pattern="^(xlsx|pdf)$"),
) -> Response:
    if format == "pdf":
        content = await export_service.export_pdf()
        media_type = "application/pdf"
        filename = "devices.pdf"
    else:
        content = await export_service.export_excel()
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        filename = "devices.xlsx"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/devices/import/template")
async def download_import_template(
    export_service: Annotated[DeviceExportService, Depends(get_device_export_service)],
    _: Annotated[User, Depends(require_permissions("device:import"))],
) -> Response:
    content = export_service.import_template_excel()
    return Response(
        content=content,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": 'attachment; filename="device_import_template.xlsx"'},
    )


@router.post("/devices/import", response_model=ApiResponse[ImportResult])
async def import_devices(
    export_service: Annotated[DeviceExportService, Depends(get_device_export_service)],
    current_user: Annotated[User, Depends(require_permissions("device:import"))],
    file: UploadFile = File(...),
) -> ApiResponse[ImportResult]:
    content = await file.read()
    data = await export_service.import_excel(content, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/devices/batch-delete", response_model=ApiResponse[DeviceBatchDeleteResult])
async def batch_delete_devices(
    payload: DeviceBatchDeleteRequest,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:delete"))],
) -> ApiResponse[DeviceBatchDeleteResult]:
    data = await service.batch_delete(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/devices/{device_id}", response_model=ApiResponse[DeviceResponse])
async def get_device(
    device_id: uuid.UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
) -> ApiResponse[DeviceResponse]:
    data = await service.get_device(device_id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/devices", response_model=ApiResponse[DeviceResponse], status_code=201)
async def create_device(
    payload: DeviceCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:create"))],
) -> ApiResponse[DeviceResponse]:
    data = await service.create_device(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/devices/{device_id}", response_model=ApiResponse[DeviceResponse])
async def update_device(
    device_id: uuid.UUID,
    payload: DeviceUpdate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[DeviceResponse]:
    data = await service.update_device(device_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/devices/{device_id}", response_model=ApiResponse[dict[str, str]])
async def delete_device(
    device_id: uuid.UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:delete"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_device(device_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


# —— device types ——
@router.get("/device-types", response_model=PaginatedResponse[DeviceTypeResponse])
async def list_device_types(
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[DeviceTypeResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_types(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("/device-types", response_model=ApiResponse[DeviceTypeResponse], status_code=201)
async def create_device_type(
    payload: DeviceTypeCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[DeviceTypeResponse]:
    data = await service.create_type(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/device-types/{type_id}", response_model=ApiResponse[DeviceTypeResponse])
async def update_device_type(
    type_id: uuid.UUID,
    payload: DeviceTypeUpdate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[DeviceTypeResponse]:
    data = await service.update_type(type_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/device-types/{type_id}", response_model=ApiResponse[dict[str, str]])
async def delete_device_type(
    type_id: uuid.UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_type(type_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


# —— param profiles ——
@router.get("/device-param-profiles", response_model=PaginatedResponse[ParamProfileResponse])
async def list_param_profiles(
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[ParamProfileResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_param_profiles(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post(
    "/device-param-profiles", response_model=ApiResponse[ParamProfileResponse], status_code=201
)
async def create_param_profile(
    payload: ParamProfileCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[ParamProfileResponse]:
    data = await service.create_param_profile(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put(
    "/device-param-profiles/{profile_id}", response_model=ApiResponse[ParamProfileResponse]
)
async def update_param_profile(
    profile_id: uuid.UUID,
    payload: ParamProfileUpdate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[ParamProfileResponse]:
    data = await service.update_param_profile(profile_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/device-param-profiles/{profile_id}", response_model=ApiResponse[dict[str, str]])
async def delete_param_profile(
    profile_id: uuid.UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_param_profile(profile_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


# —— system profiles ——
@router.get(
    "/device-system-profiles", response_model=PaginatedResponse[SystemProfileResponse]
)
async def list_system_profiles(
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[SystemProfileResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_system_profiles(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post(
    "/device-system-profiles",
    response_model=ApiResponse[SystemProfileResponse],
    status_code=201,
)
async def create_system_profile(
    payload: SystemProfileCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[SystemProfileResponse]:
    data = await service.create_system_profile(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put(
    "/device-system-profiles/{profile_id}",
    response_model=ApiResponse[SystemProfileResponse],
)
async def update_system_profile(
    profile_id: uuid.UUID,
    payload: SystemProfileUpdate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[SystemProfileResponse]:
    data = await service.update_system_profile(profile_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/device-system-profiles/{profile_id}", response_model=ApiResponse[dict[str, str]])
async def delete_system_profile(
    profile_id: uuid.UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_system_profile(profile_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


# —— bmc profiles ——
@router.get("/device-bmc-profiles", response_model=PaginatedResponse[BmcProfileResponse])
async def list_bmc_profiles(
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=100, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[BmcProfileResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_bmc_profiles(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post(
    "/device-bmc-profiles", response_model=ApiResponse[BmcProfileResponse], status_code=201
)
async def create_bmc_profile(
    payload: BmcProfileCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[BmcProfileResponse]:
    data = await service.create_bmc_profile(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put(
    "/device-bmc-profiles/{profile_id}", response_model=ApiResponse[BmcProfileResponse]
)
async def update_bmc_profile(
    profile_id: uuid.UUID,
    payload: BmcProfileUpdate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[BmcProfileResponse]:
    data = await service.update_bmc_profile(profile_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/device-bmc-profiles/{profile_id}", response_model=ApiResponse[dict[str, str]])
async def delete_bmc_profile(
    profile_id: uuid.UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_bmc_profile(profile_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())


@router.get("/manufacturers", response_model=PaginatedResponse[ManufacturerResponse])
async def list_manufacturers(
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[ManufacturerResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_manufacturers(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("/manufacturers", response_model=ApiResponse[ManufacturerResponse], status_code=201)
async def create_manufacturer(
    payload: ManufacturerCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:create"))],
) -> ApiResponse[ManufacturerResponse]:
    data = await service.create_manufacturer(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/device-models", response_model=PaginatedResponse[DeviceModelResponse])
async def list_device_models(
    service: Annotated[DeviceService, Depends(get_device_service)],
    _: Annotated[User, Depends(require_permissions("device:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[DeviceModelResponse]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_device_models(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )


@router.post("/device-models", response_model=ApiResponse[DeviceModelResponse], status_code=201)
async def create_device_model(
    payload: DeviceModelCreate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[DeviceModelResponse]:
    data = await service.create_device_model(payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.put("/device-models/{model_id}", response_model=ApiResponse[DeviceModelResponse])
async def update_device_model(
    model_id: uuid.UUID,
    payload: DeviceModelUpdate,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[DeviceModelResponse]:
    data = await service.update_device_model(model_id, payload, user_id=current_user.id)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.delete("/device-models/{model_id}", response_model=ApiResponse[dict[str, str]])
async def delete_device_model(
    model_id: uuid.UUID,
    service: Annotated[DeviceService, Depends(get_device_service)],
    current_user: Annotated[User, Depends(require_permissions("device:update"))],
) -> ApiResponse[dict[str, str]]:
    await service.delete_device_model(model_id, user_id=current_user.id)
    return ApiResponse(data={"message": "deleted"}, timestamp=datetime.now())
