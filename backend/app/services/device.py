import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.layout.engine import occupied_range
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
from app.repositories.rack import RackPositionRepository, RackRepository
from app.services.ip_address import IpAddressService
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.device import (
    DeviceBatchDeleteRequest,
    DeviceBatchDeleteResult,
    DeviceCreate,
    DeviceModelCreate,
    DeviceModelPanelApply,
    DeviceModelPanelApplyResult,
    DeviceModelResponse,
    DeviceModelUpdate,
    DevicePanelCandidate,
    DevicePanelCandidateList,
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
    ParamProfileImportResult,
    ParamDiskSpec,
    ParamProfilePayload,
    ParamProfileResponse,
    ParamProfileSyncResult,
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
    param_missing_fields,
    param_payload_summary,
    system_payload_summary,
)


def _ip_fields_from_device(
    device: Device,
) -> tuple[
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
    str | None,
]:
    """Return business/BMC/VIP display values and record/segment ids from linked rows.

    Returns:
        system_ip, bmc_ip, vip,
        system_ip_id, bmc_ip_id, vip_ip_id,
        system_segment_id, bmc_segment_id, vip_segment_id
    """
    rows = list(getattr(device, "ip_addresses", None) or [])
    if not rows:
        return None, None, None, None, None, None, None, None, None

    business = next((r for r in rows if (r.label or "") == "business"), None)
    bmc = next((r for r in rows if (r.label or "") == "bmc"), None)
    if business is None:
        business = next((r for r in rows if r.system_ip and (r.label or "") not in {"bmc", "vip"}), None)
    if bmc is None:
        # legacy: bmc stored as field on business row
        pass

    system_ip = business.system_ip if business else None
    system_ip_id = str(business.id) if business else None
    system_segment_id = str(business.segment_id) if business and business.segment_id else None

    bmc_ip = bmc.system_ip if bmc else (business.bmc_ip if business else None)
    bmc_ip_id = str(bmc.id) if bmc else None
    bmc_segment_id = str(bmc.segment_id) if bmc and bmc.segment_id else None

    vip = None
    for r in rows:
        if r.vip:
            vip = r.vip
            break
    # vip_ip_id / vip_segment_id: resolve by matching vip string against pool later in enrich if needed
    return (
        system_ip,
        bmc_ip,
        vip,
        system_ip_id,
        bmc_ip_id,
        None,
        system_segment_id,
        bmc_segment_id,
        None,
    )


def _panel_for_device(device: Device) -> tuple[dict | None, str | None, str | None]:
    """Resolve panel layout only when the device has been explicitly bound."""
    if not getattr(device, "network_panel_bound", False):
        return None, None, None
    model = getattr(device, "model", None)
    if not model or not getattr(model, "port_layout", None):
        return None, None, None
    apply_name = (getattr(model, "apply_device_name", None) or "").strip() or None
    return (
        model.port_layout,
        getattr(model, "network_kind", None),
        apply_name,
    )


def _to_device_response(
    device: Device,
    *,
    rack_code: str | None = None,
    room_id: str | None = None,
    room_name: str | None = None,
    vip_ip_id: str | None = None,
    vip_segment_id: str | None = None,
) -> DeviceResponse:
    model = device.model
    mfg = model.manufacturer if model else None
    contract = getattr(device, "contract", None)
    (
        system_ip,
        bmc_ip,
        vip,
        system_ip_id,
        bmc_ip_id,
        _vip_id,
        system_segment_id,
        bmc_segment_id,
        _vip_seg,
    ) = _ip_fields_from_device(device)
    port_layout, network_kind, panel_name = _panel_for_device(device)
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
        device_type_code=device.device_type.code if device.device_type else None,
        param_profile_id=str(device.param_profile_id) if device.param_profile_id else None,
        system_profile_id=str(device.system_profile_id) if device.system_profile_id else None,
        bmc_profile_id=str(device.bmc_profile_id) if device.bmc_profile_id else None,
        contract_id=str(device.contract_id) if device.contract_id else None,
        contract_no=contract.contract_no if contract else None,
        project_no=contract.project_no if contract else None,
        ip_summary=system_ip,
        bmc_ip=bmc_ip,
        vip=vip,
        system_ip_id=system_ip_id,
        bmc_ip_id=bmc_ip_id,
        vip_ip_id=vip_ip_id,
        system_segment_id=system_segment_id,
        bmc_segment_id=bmc_segment_id,
        vip_segment_id=vip_segment_id,
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
        port_layout=port_layout,
        network_kind=network_kind,
        panel_apply_device_name=panel_name,
        network_panel_bound=bool(getattr(device, "network_panel_bound", False)),
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
        self.position_repo = RackPositionRepository(session)
        self.room_repo = RoomRepository(session)
        self.ip_service = IpAddressService(session)

    async def _clear_mount_for_delete(
        self, device: Device, user_id: uuid.UUID | None = None
    ) -> None:
        """Clear rack occupancy so a mounted device can be soft-deleted."""
        if not device.rack_id:
            return
        if device.u_position is not None:
            positions = await self.position_repo.list_by_rack(device.rack_id)
            target_us = occupied_range(device.u_position, device.height_u)
            for pos in positions:
                if pos.u_position in target_us and pos.device_id == device.id:
                    pos.occupied = False
                    pos.device_id = None
                    pos.updated_by = user_id
        device.rack_id = None
        device.u_position = None
        device.status = DeviceStatus.STOCK.value
        device.updated_by = user_id
        device.version += 1

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
        vip_ip_id = None
        vip_segment_id = None
        _, _, vip, *_ = _ip_fields_from_device(device)
        if vip:
            vip_row = await self.ip_service.repo.get_by_system_ip(vip)
            if vip_row:
                vip_ip_id = str(vip_row.id)
                vip_segment_id = str(vip_row.segment_id) if vip_row.segment_id else None
        return _to_device_response(
            device,
            rack_code=rack_code,
            room_id=room_id,
            room_name=room_name,
            vip_ip_id=vip_ip_id,
            vip_segment_id=vip_segment_id,
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
        existing_sn = await self.repo.get_by_serial_including_deleted(payload.serial_number)
        if existing_sn and existing_sn.deleted_at is None:
            raise ConflictError("序列号已存在", code=10003)
        if existing_sn and existing_sn.deleted_at is not None:
            await self.repo.free_unique_for_soft_deleted(existing_sn)

        name = (payload.name or payload.hostname or payload.serial_number).strip()
        hostname = (payload.hostname or name).strip()
        existing_hn = await self.repo.get_by_hostname_including_deleted(hostname)
        if existing_hn and existing_hn.deleted_at is None:
            raise ConflictError("主机名已存在")
        if existing_hn and existing_hn.deleted_at is not None:
            await self.repo.free_unique_for_soft_deleted(existing_hn)

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
        if payload.system_ip_id or payload.bmc_ip_id or payload.vip_ip_id:
            await self.ip_service.assign_device_ips(
                created.id,
                system_ip_id=payload.system_ip_id,
                bmc_ip_id=payload.bmc_ip_id,
                vip_ip_id=payload.vip_ip_id,
                user_id=user_id,
            )
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

        data = payload.model_dump(exclude_unset=True)
        if any(k in data for k in ("system_ip_id", "bmc_ip_id", "vip_ip_id")):
            await self.ip_service.assign_device_ips(
                device_id,
                system_ip_id=data.get("system_ip_id"),
                bmc_ip_id=data.get("bmc_ip_id"),
                vip_ip_id=data.get("vip_ip_id"),
                user_id=user_id,
                replace_existing=True,
            )

        device = await self.repo.get_by_id_with_model(device_id)
        assert device is not None
        return await self._enrich(device)

    async def delete_device(
        self, device_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        device = await self.repo.get_by_id_with_model(device_id)
        if not device:
            raise NotFoundError("Device not found", code=10003)
        await self._clear_mount_for_delete(device, user_id=user_id)
        await self.ip_service.release_by_device(device_id, user_id=user_id)
        await self.repo.soft_delete(device, deleted_by=user_id)
        await self.repo.free_unique_for_soft_deleted(device)

    async def batch_delete(
        self, payload: DeviceBatchDeleteRequest, user_id: uuid.UUID | None = None
    ) -> DeviceBatchDeleteResult:
        result = DeviceBatchDeleteResult()
        seen: set[uuid.UUID] = set()
        to_delete: list[uuid.UUID] = []
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
            to_delete.append(device_id)
        if to_delete:
            for device_id in to_delete:
                device = await self.repo.get_by_id(device_id)
                if not device:
                    result.skipped += 1
                    continue
                await self._clear_mount_for_delete(device, user_id=user_id)
            await self.ip_service.release_by_devices(to_delete, user_id=user_id)
            for device_id in to_delete:
                device = await self.repo.get_by_id(device_id)
                if not device:
                    result.skipped += 1
                    continue
                await self.repo.soft_delete(device, deleted_by=user_id)
                await self.repo.free_unique_for_soft_deleted(device)
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
        try:
            missing = param_missing_fields(typed)
        except Exception:  # noqa: BLE001
            missing = ["系统盘", "数据盘"]
        try:
            summary = param_payload_summary(typed)
        except Exception:  # noqa: BLE001
            summary = None
        return ParamProfileResponse(
            id=str(entity.id),
            code=entity.code,
            name=entity.name,
            payload=typed,
            description=entity.description,
            summary=summary,
            is_complete=not missing,
            missing_fields=missing,
            source_device_name=(typed.source_device_name if typed else None) or entity.name,
            source_device_model=typed.source_device_model if typed else None,
            source_manufacturer=typed.source_manufacturer if typed else None,
            device_type_id=typed.device_type_id if typed else None,
            detail_params=(
                (typed.detail_params if typed and typed.detail_params else None)
                or (typed.source_device_model if typed else None)
            ),
            other_params=typed.other_params if typed else None,
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

    @staticmethod
    def _param_source_key(device_name: str, device_model: str | None = None) -> str:
        """设备参数与采购汇总按「设备名称」一一对应。"""
        return (device_name or "").strip().lower()

    @staticmethod
    def _slug_code(device_name: str, device_model: str | None = None) -> str:
        """生成仅含 ASCII 的档案编码，避免中文编码在部分环境下异常。"""
        import hashlib
        import re
        import unicodedata

        raw = (device_name or "").strip() or "device"
        digest = hashlib.md5(raw.encode("utf-8")).hexdigest()[:8]
        # 尽量保留可读英文/数字；中文名称用 hash 保证唯一
        ascii_part = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^A-Za-z0-9_-]+", "-", ascii_part).strip("-_")
        if not slug:
            slug = "dev"
        return f"P-{slug[:24]}-{digest}"[:50]

    def _index_param_profiles(
        self, entities: list[DeviceParamProfile]
    ) -> dict[str, DeviceParamProfile]:
        """以设备名称为唯一键建立索引（与采购汇总一一对应）。"""
        index: dict[str, DeviceParamProfile] = {}
        for entity in entities:
            typed: ParamProfilePayload | None = None
            if entity.payload and isinstance(entity.payload, dict):
                try:
                    typed = ParamProfilePayload.model_validate(entity.payload)
                except Exception:  # noqa: BLE001
                    typed = None
            name = (
                (typed.source_device_name if typed and typed.source_device_name else None)
                or entity.name
                or ""
            ).strip()
            key = self._param_source_key(name)
            if key and key not in index:
                index[key] = entity
        return index

    async def sync_param_profiles_from_contracts(
        self, user_id: uuid.UUID | None = None
    ) -> ParamProfileSyncResult:
        """按采购汇总「设备名称」新建空待填参数；已存在同名则跳过。"""
        from app.services.device_contract import DeviceContractService

        contract_service = DeviceContractService(self.session)
        summary = await contract_service.summary()

        unique_names: dict[str, str] = {}
        for row in summary:
            device_name = (row.device_name or "").strip()
            if not device_name:
                continue
            # 名称字段最长 100
            device_name = device_name[:100]
            key = self._param_source_key(device_name)
            unique_names.setdefault(key, device_name)

        existing = await self.param_repo.list_all()
        index = self._index_param_profiles(existing)
        created = 0
        skipped = 0
        messages: list[str] = []

        for key, device_name in unique_names.items():
            if key in index:
                skipped += 1
                continue

            code = self._slug_code(device_name)
            suffix = 1
            while await self.param_repo.get_by_code(code):
                code = f"{self._slug_code(device_name)[:40]}-{suffix}"[:50]
                suffix += 1

            # 空待填：仅溯源名称 + 磁盘占位，无 CPU/内存/容量
            payload = ParamProfilePayload(
                source_device_name=device_name,
                disks=[
                    ParamDiskSpec(role="system"),
                    ParamDiskSpec(role="data"),
                    ParamDiskSpec(role="data"),
                ],
            )
            entity = DeviceParamProfile(
                code=code,
                name=device_name,
                payload=payload.model_dump(mode="json"),
                description="待完善：由采购汇总设备名称同步生成",
                created_by=user_id,
                updated_by=user_id,
            )
            await self.param_repo.create(entity)
            created += 1
            messages.append(f"已新建待完善项：{device_name}")
            index[key] = entity

        await self.session.flush()
        return ParamProfileSyncResult(
            created=created,
            updated=0,
            skipped=skipped,
            total_summary=len(unique_names),
            messages=messages[:50],
        )

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
        await self.session.refresh(created)
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
        await self.session.refresh(entity)
        return self._to_param_profile_response(entity)

    async def delete_param_profile(
        self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        await self._delete_profile(self.param_repo, entity_id, user_id)

    async def export_param_profiles_excel(self, *, incomplete_only: bool = False) -> bytes:
        from app.services.param_profile_export import ParamProfileExportService

        entities = await self.param_repo.list_all()
        profiles = []
        for entity in entities:
            resp = self._to_param_profile_response(entity)
            profiles.append(
                {
                    "code": resp.code,
                    "name": resp.name,
                    "description": resp.description,
                    "payload": resp.payload.model_dump(mode="json") if resp.payload else {},
                    "is_complete": resp.is_complete,
                    "missing_fields": resp.missing_fields,
                }
            )
        return ParamProfileExportService().export_excel(
            profiles, incomplete_only=incomplete_only
        )

    async def import_param_profiles_excel(
        self, content: bytes, user_id: uuid.UUID | None = None
    ) -> ParamProfileImportResult:
        from app.services.param_profile_export import (
            ParamProfileExportService,
            row_to_payload_patch,
            _cell_str,
        )

        rows, parse_errors = ParamProfileExportService().parse_excel(content)
        entities = await self.param_repo.list_all()
        by_code = {e.code: e for e in entities}
        index = self._index_param_profiles(entities)

        updated = 0
        created = 0
        skipped = 0
        errors = list(parse_errors)

        for row in rows:
            row_no = row.get("_row_no", "?")
            code = _cell_str(row.get("code"))
            name = _cell_str(row.get("name"))
            model = _cell_str(row.get("source_device_model"))
            entity = by_code.get(code) if code else None
            if entity is None and name:
                entity = index.get(self._param_source_key(name))

            existing_payload: ParamProfilePayload | None = None
            if entity and isinstance(entity.payload, dict):
                try:
                    existing_payload = ParamProfilePayload.model_validate(entity.payload)
                except Exception:  # noqa: BLE001
                    existing_payload = None

            try:
                merged = row_to_payload_patch(row, existing_payload)
                if name:
                    merged.source_device_name = merged.source_device_name or name
                raw = normalize_param_payload(merged)
            except ValueError as exc:
                errors.append(f"第{row_no}行：{exc}")
                skipped += 1
                continue

            description = _cell_str(row.get("description")) or None
            if entity is None:
                if not name:
                    errors.append(f"第{row_no}行：新建时必须提供设备名称")
                    skipped += 1
                    continue
                new_code = code or self._slug_code(name, model)
                if await self.param_repo.get_by_code(new_code):
                    new_code = f"{new_code[:43]}-i{created + 1}"[:50]
                entity = DeviceParamProfile(
                    code=new_code,
                    name=name,
                    payload=raw,
                    description=description or "参数导入创建",
                    created_by=user_id,
                    updated_by=user_id,
                )
                await self.param_repo.create(entity)
                by_code[entity.code] = entity
                index[self._param_source_key(name)] = entity
                created += 1
                continue

            entity.payload = raw
            if name:
                entity.name = name
            if description is not None:
                entity.description = description
            entity.updated_by = user_id
            entity.version += 1
            updated += 1

        await self.session.flush()
        return ParamProfileImportResult(
            updated=updated,
            created=created,
            skipped=skipped,
            errors=errors[:100],
        )

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
            port_layout=getattr(created, "port_layout", None),
            apply_device_name=getattr(created, "apply_device_name", None),
            network_kind=getattr(created, "network_kind", None),
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
            port_layout=getattr(entity, "port_layout", None),
            apply_device_name=getattr(entity, "apply_device_name", None),
            network_kind=getattr(entity, "network_kind", None),
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
        if payload.port_layout is not None:
            entity.port_layout = payload.port_layout
        if payload.apply_device_name is not None:
            name = payload.apply_device_name.strip()
            entity.apply_device_name = name or None
        if payload.network_kind is not None:
            kind = payload.network_kind.strip()
            entity.network_kind = kind or None
        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        mfg_name = entity.manufacturer.name if entity.manufacturer else None
        return self._to_model_response(entity, mfg_name)

    async def list_panel_candidates(
        self,
        *,
        apply_device_name: str,
        model_id: uuid.UUID | None = None,
    ) -> DevicePanelCandidateList:
        name = apply_device_name.strip()
        if not name and not model_id:
            raise ValidationError("设备名称不能为空", code=10004)
        devices = await self.repo.list_for_panel_apply(
            apply_device_name=name or None,
            model_id=model_id,
        )
        items: list[DevicePanelCandidate] = []
        unbound = 0
        bound = 0
        for d in devices:
            is_bound = bool(getattr(d, "network_panel_bound", False))
            if is_bound:
                bound += 1
            else:
                unbound += 1
            model = getattr(d, "model", None)
            items.append(
                DevicePanelCandidate(
                    id=str(d.id),
                    name=d.name,
                    hostname=d.hostname,
                    serial_number=d.serial_number,
                    device_model_id=str(d.device_model_id),
                    device_model_name=model.name if model else None,
                    network_panel_bound=is_bound,
                    rack_code=None,
                    room_name=None,
                    u_position=d.u_position,
                    status=d.status,
                )
            )
        # Enrich rack/room labels
        rack_ids = [d.rack_id for d in devices if d.rack_id]
        if rack_ids:
            racks = await self.rack_repo.list_by_ids(list({r for r in rack_ids if r}))
            rack_map = {r.id: r for r in racks}
            room_ids = list({r.room_id for r in racks})
            rooms = await self.room_repo.list_by_ids(room_ids)
            room_map = {r.id: r for r in rooms}
            for i, d in enumerate(devices):
                if not d.rack_id:
                    continue
                rack = rack_map.get(d.rack_id)
                if not rack:
                    continue
                items[i].rack_code = rack.code
                room = room_map.get(rack.room_id)
                items[i].room_name = room.name if room else None
        return DevicePanelCandidateList(
            apply_device_name=name,
            items=items,
            unbound_count=unbound,
            bound_count=bound,
        )

    async def apply_device_model_panel(
        self,
        model_id: uuid.UUID,
        payload: DeviceModelPanelApply,
        user_id: uuid.UUID | None = None,
    ) -> DeviceModelPanelApplyResult:
        """Apply or modify network panel for selected inventory devices."""
        entity = await self.model_repo.get_by_id_with_mfg(model_id)
        if not entity:
            raise NotFoundError("设备型号不存在")
        apply_name = payload.apply_device_name.strip()
        if not apply_name:
            raise ValidationError("应用设备名称不能为空", code=10004)
        mode = payload.mode or "apply"

        # Always refresh shared layout on the catalog model
        entity.port_layout = payload.port_layout
        entity.apply_device_name = apply_name
        if payload.network_kind is not None:
            kind = payload.network_kind.strip()
            entity.network_kind = kind or None
        height = None
        if isinstance(payload.port_layout, dict):
            raw_h = payload.port_layout.get("height_u")
            if isinstance(raw_h, int) and 1 <= raw_h <= 10:
                height = raw_h
                entity.height_u = raw_h
        entity.updated_by = user_id
        entity.version += 1

        candidates = await self.repo.list_for_panel_apply(
            apply_device_name=apply_name,
            model_id=entity.id,
        )
        if not candidates and payload.device_ids:
            # 允许直接按所选 ID 应用（前端已列出）
            try:
                ids = [uuid.UUID(i) for i in payload.device_ids]
            except ValueError as exc:
                raise ValidationError("设备 ID 格式无效", code=10004) from exc
            candidates = await self.repo.list_by_ids_for_list(ids)
        if not candidates:
            raise ValidationError(
                f"未找到与采购汇总设备名称「{apply_name}」对应的台账设备",
                code=10004,
            )

        selected_ids: set[uuid.UUID] | None = None
        if payload.device_ids:
            try:
                selected_ids = {uuid.UUID(i) for i in payload.device_ids}
            except ValueError as exc:
                raise ValidationError("设备 ID 格式无效", code=10004) from exc
            # 补齐不在候选集中的所选设备
            missing = selected_ids - {d.id for d in candidates}
            if missing:
                extra = await self.repo.list_by_ids_for_list(list(missing))
                candidates = [*candidates, *extra]
            unknown = selected_ids - {d.id for d in candidates}
            if unknown:
                raise ValidationError("所选设备不存在或已删除", code=10004)

        applied_ids: list[str] = []
        modified_ids: list[str] = []
        skipped_ids: list[str] = []

        for device in candidates:
            if selected_ids is not None and device.id not in selected_ids:
                continue
            is_bound = bool(getattr(device, "network_panel_bound", False))
            if mode == "apply":
                if is_bound:
                    skipped_ids.append(str(device.id))
                    continue
                device.device_model_id = entity.id
                device.network_panel_bound = True
                if height is not None:
                    device.height_u = height
                device.updated_by = user_id
                device.version += 1
                applied_ids.append(str(device.id))
            else:  # modify
                if not is_bound:
                    skipped_ids.append(str(device.id))
                    continue
                # 已绑定设备：更新型号指向与高度，布局已写到 model
                if device.device_model_id != entity.id:
                    device.device_model_id = entity.id
                if height is not None:
                    device.height_u = height
                device.updated_by = user_id
                device.version += 1
                modified_ids.append(str(device.id))

        if mode == "apply" and not applied_ids and skipped_ids and selected_ids is not None:
            raise ValidationError("所选设备均已应用面板，请使用「修改」更新", code=10004)
        if mode == "apply" and not applied_ids and selected_ids is None and skipped_ids:
            raise ValidationError("同名设备均已应用面板，请使用「修改」更新", code=10004)
        if mode == "modify" and not modified_ids:
            raise ValidationError("没有可修改的已应用设备", code=10004)

        await self.session.flush()
        touched = applied_ids if mode == "apply" else modified_ids
        if mode == "apply":
            msg = f"已应用面板到 {len(applied_ids)} 台设备"
            if skipped_ids:
                msg += f"，跳过已应用 {len(skipped_ids)} 台"
        else:
            msg = f"已修改 {len(modified_ids)} 台已应用设备的面板"
            if skipped_ids:
                msg += f"，跳过未应用 {len(skipped_ids)} 台"

        return DeviceModelPanelApplyResult(
            device_model_id=str(entity.id),
            apply_device_name=apply_name,
            mode=mode,
            matched_device_count=len(touched),
            matched_device_ids=touched,
            applied_count=len(applied_ids),
            modified_count=len(modified_ids),
            skipped_count=len(skipped_ids),
            skipped_device_ids=skipped_ids,
            message=msg,
        )

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
                    port_layout=getattr(full or i, "port_layout", None),
                    apply_device_name=getattr(full or i, "apply_device_name", None),
                    network_kind=getattr(full or i, "network_kind", None),
                    created_at=i.created_at,
                )
            )
        return result, pagination
