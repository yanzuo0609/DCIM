import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.device import (
    Device,
    DeviceBmcProfile,
    DeviceModel,
    DeviceParamProfile,
    DeviceStatus,
    DeviceSystemProfile,
    DeviceType,
    Manufacturer,
)
from app.repositories.device import (
    DeviceBmcProfileRepository,
    DeviceCategoryRepository,
    DeviceModelRepository,
    DeviceParamProfileRepository,
    DeviceRepository,
    DeviceSystemProfileRepository,
    DeviceTypeRepository,
    ManufacturerRepository,
)
from app.repositories.device_contract import DeviceContractRepository
from app.repositories.infrastructure import RoomRepository
from app.repositories.rack import RackRepository
from app.schemas.common import PaginationMeta, PaginationParams
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
    ParamProfilePayload,
    ParamProfileResponse,
    ParamProfileUpdate,
    ProfileCreate,
    ProfileResponse,
    ProfileUpdate,
    SystemProfileCreate,
    SystemProfileResponse,
    SystemProfileUpdate,
    bmc_payload_summary,
    mask_bmc_payload,
    mask_system_payload,
    normalize_bmc_payload,
    normalize_param_payload,
    normalize_system_payload,
    param_payload_summary,
    system_payload_summary,
)


def _ip_fields_from_device(device: Device) -> tuple[str | None, str | None, str | None]:
    """Return (system_ip, bmc_ip, vip) from linked ip_address rows."""
    rows = list(getattr(device, "ip_addresses", None) or [])
    if not rows:
        return None, None, None
    # Prefer first bound record with system_ip
    primary = rows[0]
    for row in rows:
        if row.system_ip:
            primary = row
            break
    return primary.system_ip, primary.bmc_ip, primary.vip


def _to_device_response(
    device: Device,
    *,
    rack_code: str | None = None,
    room_id: str | None = None,
    room_name: str | None = None,
) -> DeviceResponse:
    model = device.model
    mfg = model.manufacturer if model else None
    contract = getattr(device, "contract", None)
    system_ip, bmc_ip, vip = _ip_fields_from_device(device)
    return DeviceResponse(
        id=str(device.id),
        name=device.name or device.hostname,
        hostname=device.hostname,
        serial_number=device.serial_number,
        device_model_id=str(device.device_model_id),
        device_model_name=model.name if model else None,
        manufacturer_id=str(mfg.id) if mfg else None,
        manufacturer_name=mfg.name if mfg else None,
        device_type_id=str(device.device_type_id) if device.device_type_id else None,
        device_type_name=device.device_type.name if device.device_type else None,
        param_profile_id=str(device.param_profile_id) if device.param_profile_id else None,
        system_profile_id=str(device.system_profile_id) if device.system_profile_id else None,
        bmc_profile_id=str(device.bmc_profile_id) if device.bmc_profile_id else None,
        contract_id=str(device.contract_id) if device.contract_id else None,
        contract_no=contract.contract_no if contract else None,
        project_no=contract.project_no if contract else None,
        ip_summary=system_ip,
        bmc_ip=bmc_ip,
        vip=vip,
        rack_id=str(device.rack_id) if device.rack_id else None,
        rack_code=rack_code,
        room_id=room_id,
        room_name=room_name,
        u_position=device.u_position,
        height_u=device.height_u,
        weight=device.weight,
        power=device.power,
        status=device.status,
        description=device.description,
        created_at=device.created_at,
        updated_at=device.updated_at,
    )


class DeviceService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = DeviceRepository(session)
        self.model_repo = DeviceModelRepository(session)
        self.mfg_repo = ManufacturerRepository(session)
        self.cat_repo = DeviceCategoryRepository(session)
        self.type_repo = DeviceTypeRepository(session)
        self.param_repo = DeviceParamProfileRepository(session)
        self.system_repo = DeviceSystemProfileRepository(session)
        self.bmc_repo = DeviceBmcProfileRepository(session)
        self.contract_repo = DeviceContractRepository(session)
        self.rack_repo = RackRepository(session)
        self.room_repo = RoomRepository(session)

    async def _resolve_contract_id(self, contract_id: str | None) -> uuid.UUID | None:
        if not contract_id:
            return None
        contract = await self.contract_repo.get_by_id(uuid.UUID(contract_id))
        if not contract:
            raise NotFoundError("合同信息不存在")
        return contract.id

    async def _enrich(self, device: Device) -> DeviceResponse:
        rack_code = None
        room_id = None
        room_name = None
        if device.rack_id:
            rack = await self.rack_repo.get_by_id(device.rack_id)
            if rack:
                rack_code = rack.code
                room_id = str(rack.room_id)
                room = await self.room_repo.get_by_id(rack.room_id)
                if room:
                    room_name = room.name
        return _to_device_response(
            device, rack_code=rack_code, room_id=room_id, room_name=room_name
        )

    async def _enrich_many(self, devices: list[Device]) -> list[DeviceResponse]:
        """Batch-enrich devices with rack/room labels (avoids N+1)."""
        rack_ids = list({d.rack_id for d in devices if d.rack_id})
        racks = await self.rack_repo.list_by_ids(rack_ids)
        rack_map = {r.id: r for r in racks}
        room_ids = list({r.room_id for r in racks})
        rooms = await self.room_repo.list_by_ids(room_ids)
        room_map = {r.id: r for r in rooms}
        result: list[DeviceResponse] = []
        for device in devices:
            rack_code = None
            room_id = None
            room_name = None
            if device.rack_id:
                rack = rack_map.get(device.rack_id)
                if rack:
                    rack_code = rack.code
                    room_id = str(rack.room_id)
                    room = room_map.get(rack.room_id)
                    if room:
                        room_name = room.name
            result.append(
                _to_device_response(
                    device, rack_code=rack_code, room_id=room_id, room_name=room_name
                )
            )
        return result

    async def list_devices(
        self,
        params: PaginationParams,
        rack_id: uuid.UUID | None = None,
        room_id: uuid.UUID | None = None,
        status: str | None = None,
    ) -> tuple[list[DeviceResponse], PaginationMeta]:
        filters: dict = {}
        if rack_id:
            filters["rack_id"] = rack_id
        if status:
            filters["status"] = status
        if room_id and not rack_id:
            items, total = await self.repo.list_paginated_by_room(
                room_id,
                page=params.page,
                page_size=params.page_size,
                keyword=params.keyword,
                sort=params.sort or "created_at",
                order=params.order or "desc",
                status=status,
            )
        else:
            items, total = await self.repo.list_paginated(
                page=params.page,
                page_size=params.page_size,
                keyword=params.keyword,
                sort=params.sort,
                order=params.order,
                filters=filters or None,
                search_fields=["hostname", "serial_number", "name"],
            )
        full_devices = await self.repo.list_by_ids_for_list([item.id for item in items])
        device_map = {d.id: d for d in full_devices}
        ordered = [device_map[item.id] for item in items if item.id in device_map]
        enriched = await self._enrich_many(ordered)
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return enriched, pagination

    async def get_device(self, device_id: uuid.UUID) -> DeviceResponse:
        device = await self.repo.get_by_id_with_model(device_id)
        if not device:
            raise NotFoundError("Device not found", code=10003)
        return await self._enrich(device)

    async def create_device(
        self, payload: DeviceCreate, user_id: uuid.UUID | None = None
    ) -> DeviceResponse:
        if await self.repo.get_by_serial(payload.serial_number):
            raise ConflictError("序列号已存在", code=10003)

        name = (payload.name or payload.hostname or payload.serial_number).strip()
        hostname = (payload.hostname or name).strip()
        if await self.repo.get_by_hostname(hostname):
            raise ConflictError("主机名已存在")

        model = await self.model_repo.get_by_id(uuid.UUID(payload.device_model_id))
        if not model:
            raise NotFoundError("Device model not found")

        type_id = uuid.UUID(payload.device_type_id) if payload.device_type_id else None
        if type_id and not await self.type_repo.get_by_id(type_id):
            raise NotFoundError("设备类型不存在")

        height_u = payload.height_u or model.height_u
        contract_id = await self._resolve_contract_id(payload.contract_id)
        entity = Device(
            name=name,
            hostname=hostname,
            serial_number=payload.serial_number,
            device_model_id=model.id,
            device_type_id=type_id,
            param_profile_id=uuid.UUID(payload.param_profile_id) if payload.param_profile_id else None,
            system_profile_id=uuid.UUID(payload.system_profile_id) if payload.system_profile_id else None,
            bmc_profile_id=uuid.UUID(payload.bmc_profile_id) if payload.bmc_profile_id else None,
            contract_id=contract_id,
            height_u=height_u,
            weight=payload.weight or model.weight,
            power=payload.power or model.power,
            status=DeviceStatus.STOCK.value,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        device = await self.repo.get_by_id_with_model(created.id)
        assert device is not None
        return await self._enrich(device)

    async def update_device(
        self,
        device_id: uuid.UUID,
        payload: DeviceUpdate,
        user_id: uuid.UUID | None = None,
    ) -> DeviceResponse:
        device = await self.repo.get_by_id_with_model(device_id)
        if not device:
            raise NotFoundError("Device not found", code=10003)

        if payload.name is not None:
            device.name = payload.name
        if payload.hostname and payload.hostname != device.hostname:
            if await self.repo.get_by_hostname(payload.hostname):
                raise ConflictError("主机名已存在")
            device.hostname = payload.hostname
        if payload.serial_number and payload.serial_number != device.serial_number:
            if await self.repo.get_by_serial(payload.serial_number):
                raise ConflictError("序列号已存在")
            device.serial_number = payload.serial_number
        if payload.device_model_id:
            model = await self.model_repo.get_by_id(uuid.UUID(payload.device_model_id))
            if not model:
                raise NotFoundError("Device model not found")
            device.device_model_id = model.id
        if payload.device_type_id is not None:
            if payload.device_type_id == "":
                device.device_type_id = None
            else:
                type_id = uuid.UUID(payload.device_type_id)
                if not await self.type_repo.get_by_id(type_id):
                    raise NotFoundError("设备类型不存在")
                device.device_type_id = type_id
        if payload.param_profile_id is not None:
            device.param_profile_id = (
                uuid.UUID(payload.param_profile_id) if payload.param_profile_id else None
            )
        if payload.system_profile_id is not None:
            device.system_profile_id = (
                uuid.UUID(payload.system_profile_id) if payload.system_profile_id else None
            )
        if payload.bmc_profile_id is not None:
            device.bmc_profile_id = (
                uuid.UUID(payload.bmc_profile_id) if payload.bmc_profile_id else None
            )
        if payload.contract_id is not None:
            if payload.contract_id == "":
                device.contract_id = None
            else:
                device.contract_id = await self._resolve_contract_id(payload.contract_id)
        if payload.height_u is not None:
            device.height_u = payload.height_u
        if payload.weight is not None:
            device.weight = payload.weight
        if payload.power is not None:
            device.power = payload.power
        if payload.status is not None:
            device.status = payload.status
        if payload.description is not None:
            device.description = payload.description

        device.updated_by = user_id
        device.version += 1
        await self.session.flush()
        device = await self.repo.get_by_id_with_model(device_id)
        assert device is not None
        return await self._enrich(device)

    async def delete_device(
        self, device_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        device = await self.repo.get_by_id_with_model(device_id)
        if not device:
            raise NotFoundError("Device not found", code=10003)
        if device.rack_id:
            raise ConflictError("请先下架设备再删除")
        await self.repo.soft_delete(device, deleted_by=user_id)

    async def batch_delete(
        self, payload: DeviceBatchDeleteRequest, user_id: uuid.UUID | None = None
    ) -> DeviceBatchDeleteResult:
        result = DeviceBatchDeleteResult()
        seen: set[uuid.UUID] = set()
        for raw in payload.ids:
            try:
                device_id = uuid.UUID(raw)
            except ValueError:
                result.skipped += 1
                result.errors.append(f"{raw}: 无效 ID")
                continue
            if device_id in seen:
                continue
            seen.add(device_id)
            device = await self.repo.get_by_id_with_model(device_id)
            if not device:
                result.skipped += 1
                result.errors.append(f"{raw}: 不存在")
                continue
            if device.rack_id:
                result.skipped += 1
                result.errors.append(f"{device.hostname}: 已上架，无法删除")
                continue
            await self.repo.soft_delete(device, deleted_by=user_id)
            result.deleted += 1
        await self.session.flush()
        return result

    # —— types ——
    async def list_types(self, params: PaginationParams) -> tuple[list[DeviceTypeResponse], PaginationMeta]:
        items, total = await self.type_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["code", "name"],
            sort="code",
            order="asc",
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [
            DeviceTypeResponse(
                id=str(i.id),
                code=i.code,
                name=i.name,
                is_system=i.is_system,
                description=i.description,
                created_at=i.created_at,
                updated_at=i.updated_at,
            )
            for i in items
        ], pagination

    async def create_type(
        self, payload: DeviceTypeCreate, user_id: uuid.UUID | None = None
    ) -> DeviceTypeResponse:
        code = payload.code.strip()
        name = payload.name.strip()
        if not code or not name:
            raise ValidationError("类型编码与名称不能为空", code=10004)
        if await self.type_repo.get_by_code(code):
            raise ConflictError("设备类型编码已存在")
        entity = DeviceType(
            code=code,
            name=name,
            is_system=False,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.type_repo.create(entity)
        return DeviceTypeResponse(
            id=str(created.id),
            code=created.code,
            name=created.name,
            is_system=created.is_system,
            description=created.description,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )

    async def update_type(
        self, type_id: uuid.UUID, payload: DeviceTypeUpdate, user_id: uuid.UUID | None = None
    ) -> DeviceTypeResponse:
        entity = await self.type_repo.get_by_id(type_id)
        if not entity:
            raise NotFoundError("设备类型不存在")
        if payload.code is not None:
            if entity.is_system:
                raise ValidationError("系统内置类型编码不可修改", code=10004)
            code = payload.code.strip()
            if not code:
                raise ValidationError("类型编码不能为空", code=10004)
            existing = await self.type_repo.get_by_code(code)
            if existing and existing.id != entity.id:
                raise ConflictError("设备类型编码已存在")
            entity.code = code
        if payload.name is not None:
            entity.name = payload.name.strip()
        if payload.description is not None:
            entity.description = payload.description
        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        return DeviceTypeResponse(
            id=str(entity.id),
            code=entity.code,
            name=entity.name,
            is_system=entity.is_system,
            description=entity.description,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def delete_type(self, type_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.type_repo.get_by_id(type_id)
        if not entity:
            raise NotFoundError("设备类型不存在")
        if entity.is_system:
            raise ValidationError("系统内置类型不可删除", code=10004)
        used = await self.type_repo.count_devices(type_id)
        if used:
            raise ValidationError(f"仍有 {used} 台设备使用该类型，无法删除", code=10004)
        await self.type_repo.soft_delete(entity, deleted_by=user_id)

    # —— profiles helpers ——
    def _to_param_profile_response(self, entity: DeviceParamProfile) -> ParamProfileResponse:
        typed: ParamProfilePayload | None = None
        if entity.payload and isinstance(entity.payload, dict):
            try:
                typed = ParamProfilePayload.model_validate(entity.payload)
            except Exception:  # noqa: BLE001
                typed = None
        return ParamProfileResponse(
            id=str(entity.id),
            code=entity.code,
            name=entity.name,
            payload=typed,
            description=entity.description,
            summary=param_payload_summary(typed),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list_param_profiles(
        self, params: PaginationParams
    ) -> tuple[list[ParamProfileResponse], PaginationMeta]:
        items, total = await self.param_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["code", "name"],
            sort="code",
            order="asc",
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [self._to_param_profile_response(i) for i in items], pagination

    async def create_param_profile(
        self, payload: ParamProfileCreate, user_id: uuid.UUID | None = None
    ) -> ParamProfileResponse:
        if await self.param_repo.get_by_code(payload.code):
            raise ConflictError("档案编码已存在")
        try:
            raw_payload = normalize_param_payload(payload.payload)
        except ValueError as exc:
            raise ValidationError(str(exc), code=10004) from exc
        entity = DeviceParamProfile(
            code=payload.code,
            name=payload.name,
            payload=raw_payload,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.param_repo.create(entity)
        return self._to_param_profile_response(created)

    async def update_param_profile(
        self, entity_id: uuid.UUID, payload: ParamProfileUpdate, user_id: uuid.UUID | None = None
    ) -> ParamProfileResponse:
        entity = await self.param_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("档案不存在")
        if payload.name is not None:
            entity.name = payload.name
        if payload.payload is not None:
            try:
                entity.payload = normalize_param_payload(payload.payload)
            except ValueError as exc:
                raise ValidationError(str(exc), code=10004) from exc
        if payload.description is not None:
            entity.description = payload.description
        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        return self._to_param_profile_response(entity)

    async def delete_param_profile(
        self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        await self._delete_profile(self.param_repo, entity_id, user_id)

    def _to_system_profile_response(self, entity: DeviceSystemProfile) -> SystemProfileResponse:
        raw = entity.payload if isinstance(entity.payload, dict) else None
        return SystemProfileResponse(
            id=str(entity.id),
            code=entity.code,
            name=entity.name,
            payload=mask_system_payload(raw),
            description=entity.description,
            summary=system_payload_summary(raw),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    def _to_bmc_profile_response(self, entity: DeviceBmcProfile) -> BmcProfileResponse:
        raw = entity.payload if isinstance(entity.payload, dict) else None
        return BmcProfileResponse(
            id=str(entity.id),
            code=entity.code,
            name=entity.name,
            payload=mask_bmc_payload(raw),
            description=entity.description,
            summary=bmc_payload_summary(raw),
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list_system_profiles(
        self, params: PaginationParams
    ) -> tuple[list[SystemProfileResponse], PaginationMeta]:
        items, total = await self.system_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["code", "name"],
            sort="code",
            order="asc",
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [self._to_system_profile_response(i) for i in items], pagination

    async def create_system_profile(
        self, payload: SystemProfileCreate, user_id: uuid.UUID | None = None
    ) -> SystemProfileResponse:
        if await self.system_repo.get_by_code(payload.code):
            raise ConflictError("档案编码已存在")
        try:
            raw_payload = normalize_system_payload(payload.payload)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"系统档案参数无效: {exc}", code=10004) from exc
        entity = DeviceSystemProfile(
            code=payload.code,
            name=payload.name,
            payload=raw_payload,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.system_repo.create(entity)
        return self._to_system_profile_response(created)

    async def update_system_profile(
        self, entity_id: uuid.UUID, payload: SystemProfileUpdate, user_id: uuid.UUID | None = None
    ) -> SystemProfileResponse:
        entity = await self.system_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("档案不存在")
        if payload.name is not None:
            entity.name = payload.name
        if payload.payload is not None:
            try:
                prev = entity.payload if isinstance(entity.payload, dict) else None
                entity.payload = normalize_system_payload(payload.payload, prev)
            except Exception as exc:  # noqa: BLE001
                raise ValidationError(f"系统档案参数无效: {exc}", code=10004) from exc
        if payload.description is not None:
            entity.description = payload.description
        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        return self._to_system_profile_response(entity)

    async def delete_system_profile(
        self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        await self._delete_profile(self.system_repo, entity_id, user_id)

    async def list_bmc_profiles(
        self, params: PaginationParams
    ) -> tuple[list[BmcProfileResponse], PaginationMeta]:
        items, total = await self.bmc_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["code", "name"],
            sort="code",
            order="asc",
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [self._to_bmc_profile_response(i) for i in items], pagination

    async def create_bmc_profile(
        self, payload: BmcProfileCreate, user_id: uuid.UUID | None = None
    ) -> BmcProfileResponse:
        if await self.bmc_repo.get_by_code(payload.code):
            raise ConflictError("档案编码已存在")
        try:
            raw_payload = normalize_bmc_payload(payload.payload)
        except Exception as exc:  # noqa: BLE001
            raise ValidationError(f"BMC 档案参数无效: {exc}", code=10004) from exc
        entity = DeviceBmcProfile(
            code=payload.code,
            name=payload.name,
            payload=raw_payload,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.bmc_repo.create(entity)
        return self._to_bmc_profile_response(created)

    async def update_bmc_profile(
        self, entity_id: uuid.UUID, payload: BmcProfileUpdate, user_id: uuid.UUID | None = None
    ) -> BmcProfileResponse:
        entity = await self.bmc_repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("档案不存在")
        if payload.name is not None:
            entity.name = payload.name
        if payload.payload is not None:
            try:
                prev = entity.payload if isinstance(entity.payload, dict) else None
                entity.payload = normalize_bmc_payload(payload.payload, prev)
            except Exception as exc:  # noqa: BLE001
                raise ValidationError(f"BMC 档案参数无效: {exc}", code=10004) from exc
        if payload.description is not None:
            entity.description = payload.description
        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        return self._to_bmc_profile_response(entity)

    async def delete_bmc_profile(
        self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        await self._delete_profile(self.bmc_repo, entity_id, user_id)

    async def _list_profiles(self, repo, params: PaginationParams):
        items, total = await repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["code", "name"],
            sort="code",
            order="asc",
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [
            ProfileResponse(
                id=str(i.id),
                code=i.code,
                name=i.name,
                payload=i.payload,
                description=i.description,
                created_at=i.created_at,
                updated_at=i.updated_at,
            )
            for i in items
        ], pagination

    async def _create_profile(self, repo, model_cls, payload: ProfileCreate, user_id):
        if await repo.get_by_code(payload.code):
            raise ConflictError("档案编码已存在")
        entity = model_cls(
            code=payload.code,
            name=payload.name,
            payload=payload.payload,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await repo.create(entity)
        return ProfileResponse(
            id=str(created.id),
            code=created.code,
            name=created.name,
            payload=created.payload,
            description=created.description,
            created_at=created.created_at,
            updated_at=created.updated_at,
        )

    async def _update_profile(self, repo, entity_id, payload: ProfileUpdate, user_id):
        entity = await repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("档案不存在")
        if payload.name is not None:
            entity.name = payload.name
        if payload.payload is not None:
            entity.payload = payload.payload
        if payload.description is not None:
            entity.description = payload.description
        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        return ProfileResponse(
            id=str(entity.id),
            code=entity.code,
            name=entity.name,
            payload=entity.payload,
            description=entity.description,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def _delete_profile(self, repo, entity_id, user_id):
        entity = await repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("档案不存在")
        await repo.soft_delete(entity, deleted_by=user_id)

    async def list_manufacturers(
        self, params: PaginationParams
    ) -> tuple[list[ManufacturerResponse], PaginationMeta]:
        items, total = await self.mfg_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["code", "name"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [
            ManufacturerResponse(
                id=str(i.id),
                code=i.code,
                name=i.name,
                description=i.description,
                created_at=i.created_at,
            )
            for i in items
        ], pagination

    async def create_manufacturer(
        self, payload: ManufacturerCreate, user_id: uuid.UUID | None = None
    ) -> ManufacturerResponse:
        if await self.mfg_repo.get_by_code(payload.code):
            raise ConflictError("Manufacturer code already exists")
        entity = Manufacturer(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.mfg_repo.create(entity)
        return ManufacturerResponse(
            id=str(created.id),
            code=created.code,
            name=created.name,
            description=created.description,
            created_at=created.created_at,
        )

    async def _ensure_custom_manufacturer(
        self, user_id: uuid.UUID | None = None
    ) -> Manufacturer:
        mfg = await self.mfg_repo.get_by_code("CUSTOM")
        if mfg:
            return mfg
        entity = Manufacturer(
            code="CUSTOM",
            name="自定义",
            description="用户自定义型号默认厂商",
            created_by=user_id,
            updated_by=user_id,
        )
        return await self.mfg_repo.create(entity)

    async def create_device_model(
        self, payload: DeviceModelCreate, user_id: uuid.UUID | None = None
    ) -> DeviceModelResponse:
        code = payload.code.strip()
        name = payload.name.strip()
        if not code or not name:
            raise ValidationError("型号编码与名称不能为空", code=10004)
        if await self.model_repo.get_by_code(code):
            raise ConflictError("设备型号编码已存在")
        if payload.manufacturer_id:
            mfg = await self.mfg_repo.get_by_id(uuid.UUID(payload.manufacturer_id))
            if not mfg:
                raise NotFoundError("厂商不存在")
        else:
            mfg = await self._ensure_custom_manufacturer(user_id=user_id)
        entity = DeviceModel(
            code=code,
            name=name,
            manufacturer_id=mfg.id,
            category_id=uuid.UUID(payload.category_id) if payload.category_id else None,
            height_u=payload.height_u,
            weight=payload.weight,
            power=payload.power,
            depth=payload.depth,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.model_repo.create(entity)
        return DeviceModelResponse(
            id=str(created.id),
            code=created.code,
            name=created.name,
            manufacturer_id=str(created.manufacturer_id),
            manufacturer_name=mfg.name,
            category_id=str(created.category_id) if created.category_id else None,
            height_u=created.height_u,
            weight=created.weight,
            power=created.power,
            depth=created.depth,
            description=created.description,
            created_at=created.created_at,
        )

    def _to_model_response(
        self, entity: DeviceModel, manufacturer_name: str | None = None
    ) -> DeviceModelResponse:
        return DeviceModelResponse(
            id=str(entity.id),
            code=entity.code,
            name=entity.name,
            manufacturer_id=str(entity.manufacturer_id),
            manufacturer_name=manufacturer_name,
            category_id=str(entity.category_id) if entity.category_id else None,
            height_u=entity.height_u,
            weight=entity.weight,
            power=entity.power,
            depth=entity.depth,
            description=entity.description,
            created_at=entity.created_at,
        )

    async def update_device_model(
        self,
        model_id: uuid.UUID,
        payload: DeviceModelUpdate,
        user_id: uuid.UUID | None = None,
    ) -> DeviceModelResponse:
        entity = await self.model_repo.get_by_id_with_mfg(model_id)
        if not entity:
            raise NotFoundError("设备型号不存在")
        if payload.code is not None:
            code = payload.code.strip()
            if not code:
                raise ValidationError("型号编码不能为空", code=10004)
            existing = await self.model_repo.get_by_code(code)
            if existing and existing.id != entity.id:
                raise ConflictError("设备型号编码已存在")
            entity.code = code
        if payload.name is not None:
            name = payload.name.strip()
            if not name:
                raise ValidationError("型号名称不能为空", code=10004)
            entity.name = name
        if payload.height_u is not None:
            entity.height_u = payload.height_u
        if payload.power is not None:
            entity.power = payload.power
        if payload.description is not None:
            entity.description = payload.description
        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        mfg_name = entity.manufacturer.name if entity.manufacturer else None
        return self._to_model_response(entity, mfg_name)

    async def delete_device_model(
        self, model_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        entity = await self.model_repo.get_by_id(model_id)
        if not entity:
            raise NotFoundError("设备型号不存在")
        used = await self.model_repo.count_devices(model_id)
        if used:
            raise ValidationError(f"仍有 {used} 台设备使用该型号，无法删除", code=10004)
        await self.model_repo.soft_delete(entity, deleted_by=user_id)

    async def list_device_models(
        self, params: PaginationParams
    ) -> tuple[list[DeviceModelResponse], PaginationMeta]:
        items, total = await self.model_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["code", "name"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        fulls = await self.model_repo.list_by_ids_with_mfg([i.id for i in items])
        full_map = {f.id: f for f in fulls}
        result = []
        for i in items:
            full = full_map.get(i.id)
            mfg_name = full.manufacturer.name if full and full.manufacturer else None
            result.append(
                DeviceModelResponse(
                    id=str(i.id),
                    code=i.code,
                    name=i.name,
                    manufacturer_id=str(i.manufacturer_id),
                    manufacturer_name=mfg_name,
                    category_id=str(i.category_id) if i.category_id else None,
                    height_u=i.height_u,
                    weight=i.weight,
                    power=i.power,
                    depth=i.depth,
                    description=i.description,
                    created_at=i.created_at,
                )
            )
        return result, pagination
