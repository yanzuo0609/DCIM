import ipaddress
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.layout.engine import (
    find_first_available,
    occupied_range,
    pick_mount_u,
    validate_mount,
)
from app.models.device import Device, DeviceStatus
from app.models.ip_address import IpBindType, IpStatus
from app.repositories.device import (
    DeviceModelRepository,
    DeviceRepository,
    ManufacturerRepository,
)
from app.repositories.device_contract import DeviceContractRepository
from app.repositories.infrastructure import RoomRepository
from app.repositories.ip_address import IpAddressRepository
from app.repositories.rack import RackPositionRepository, RackRepository
from app.services.ip_address import IpAddressService
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


def _ip_sort_key(value: str) -> tuple:
    try:
        return (0, int(ipaddress.ip_address(value)))
    except ValueError:
        return (1, value)


class LayoutService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.rack_repo = RackRepository(session)
        self.position_repo = RackPositionRepository(session)
        self.device_repo = DeviceRepository(session)
        self.model_repo = DeviceModelRepository(session)
        self.mfg_repo = ManufacturerRepository(session)
        self.contract_repo = DeviceContractRepository(session)
        self.room_repo = RoomRepository(session)
        self.ip_repo = IpAddressRepository(session)
        self.ip_service = IpAddressService(session)

    async def _build_occupied_map(self, rack_id: uuid.UUID) -> dict[int, uuid.UUID | None]:
        """仅统计真实占用：有 device_id 的 occupied 位。

        残留 occupied=True 但无设备的幽灵位在机柜图上显示为空闲，
        若计入占用会导致「U 位空着却上架失败」。
        """
        positions = await self.position_repo.list_by_rack(rack_id)
        occupied: dict[int, uuid.UUID | None] = {}
        for pos in positions:
            if not pos.occupied:
                continue
            if pos.device_id is None:
                # 清理幽灵占用，避免空闲 U 被误拦
                pos.occupied = False
                continue
            occupied[pos.u_position] = pos.device_id
        return occupied

    async def validate(self, payload: ValidateLayoutRequest) -> ValidateLayoutResponse:
        rack_id = uuid.UUID(payload.rack_id)
        rack = await self.rack_repo.get_by_id_with_positions(rack_id)
        if not rack:
            raise NotFoundError("Rack not found")

        exclude_id = uuid.UUID(payload.exclude_device_id) if payload.exclude_device_id else None
        occupied_map = await self._build_occupied_map(rack_id)
        result = validate_mount(
            total_u=rack.total_u,
            u_position=payload.u_position,
            height_u=payload.height_u,
            occupied_map=occupied_map,
            exclude_device_id=exclude_id,
        )
        return ValidateLayoutResponse(
            valid=result.valid,
            message=result.message,
            occupied_positions=result.occupied_positions,
        )

    async def auto_layout(
        self, payload: AutoLayoutRequest, user_id: uuid.UUID | None = None
    ) -> AutoLayoutResponse:
        rack_id = uuid.UUID(payload.rack_id)
        device_id = uuid.UUID(payload.device_id)
        rack = await self.rack_repo.get_by_id_with_positions(rack_id)
        device = await self.device_repo.get_by_id_with_model(device_id)
        if not rack:
            raise NotFoundError("Rack not found")
        if not device:
            raise NotFoundError("Device not found")

        occupied_map = await self._build_occupied_map(rack_id)
        u_position = find_first_available(
            total_u=rack.total_u,
            height_u=device.height_u,
            occupied_map=occupied_map,
        )
        if u_position is None:
            return AutoLayoutResponse(u_position=None, message="No available U space in rack")

        await self.mount(
            MountRequest(device_id=payload.device_id, rack_id=payload.rack_id, u_position=u_position),
            user_id=user_id,
        )
        return AutoLayoutResponse(u_position=u_position, message="Device mounted successfully")

    async def mount(
        self, payload: MountRequest, user_id: uuid.UUID | None = None
    ) -> ValidateLayoutResponse:
        rack_id = uuid.UUID(payload.rack_id)
        device_id = uuid.UUID(payload.device_id)

        rack = await self.rack_repo.get_by_id_with_positions(rack_id)
        device = await self.device_repo.get_by_id_with_model(device_id)
        if not rack:
            raise NotFoundError("Rack not found")
        if not device:
            raise NotFoundError("Device not found")

        if device.rack_id and device.rack_id != rack_id:
            await self.unmount(UnmountRequest(device_id=payload.device_id), user_id=user_id)
            device = await self.device_repo.get_by_id_with_model(device_id)
            assert device is not None

        occupied_map = await self._build_occupied_map(rack_id)
        validation = validate_mount(
            total_u=rack.total_u,
            u_position=payload.u_position,
            height_u=device.height_u,
            occupied_map=occupied_map,
            exclude_device_id=device_id if device.rack_id == rack_id else None,
        )
        if not validation.valid:
            raise ValidationError(validation.message, code=10004)

        positions = await self.position_repo.list_by_rack(rack_id)
        pos_map = {p.u_position: p for p in positions}
        target_us = occupied_range(payload.u_position, device.height_u)

        for u in target_us:
            pos = pos_map.get(u)
            if not pos:
                raise ValidationError(f"U position {u} not found", code=10004)
            pos.occupied = True
            pos.device_id = device_id
            pos.updated_by = user_id

        device.rack_id = rack_id
        device.u_position = payload.u_position
        device.status = DeviceStatus.MOUNTED.value
        device.updated_by = user_id
        device.version += 1
        await self.session.flush()

        return ValidateLayoutResponse(valid=True, message="Device mounted successfully")

    async def unmount(
        self, payload: UnmountRequest, user_id: uuid.UUID | None = None
    ) -> ValidateLayoutResponse:
        device_id = uuid.UUID(payload.device_id)
        device = await self.device_repo.get_by_id_with_model(device_id)
        if not device:
            raise NotFoundError("Device not found")
        if not device.rack_id or device.u_position is None:
            raise ValidationError("Device is not mounted")

        positions = await self.position_repo.list_by_rack(device.rack_id)
        target_us = occupied_range(device.u_position, device.height_u)
        for pos in positions:
            if pos.u_position in target_us and pos.device_id == device_id:
                pos.occupied = False
                pos.device_id = None
                pos.updated_by = user_id

        device.rack_id = None
        device.u_position = None
        device.status = DeviceStatus.STOCK.value
        device.updated_by = user_id
        device.version += 1
        # 标准下架：释放该设备已分配的 IP，恢复为空闲
        await self.ip_service.release_by_device(device_id, user_id=user_id)
        await self.session.flush()

        return ValidateLayoutResponse(valid=True, message="Device unmounted successfully")

    async def _resolve_batch_racks(self, payload: BatchMountRequest) -> list:
        room_id = uuid.UUID(payload.room_id)
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("机房不存在")

        racks = await self.rack_repo.list_by_room(room_id)
        if payload.rack_ids:
            wanted = {uuid.UUID(rid) for rid in payload.rack_ids}
            racks = [r for r in racks if r.id in wanted]
        if payload.row_nos:
            rows = set(payload.row_nos)
            racks = [r for r in racks if r.row_no in rows]
        if payload.column_nos:
            cols = set(payload.column_nos)
            racks = [r for r in racks if r.column_no in cols]
        racks.sort(key=lambda r: (r.row_no, r.column_no, r.code))
        return racks

    async def batch_mount(
        self, payload: BatchMountRequest, user_id: uuid.UUID | None = None
    ) -> BatchMountResult:
        result = BatchMountResult()
        if not payload.device_ids and not payload.new_devices:
            raise ValidationError("请选择库存设备或提供新建设备", code=10004)

        racks = await self._resolve_batch_racks(payload)
        if not racks:
            raise ValidationError("未找到可用机柜", code=10004)

        queue: list[uuid.UUID] = []
        seen: set[uuid.UUID] = set()

        for raw in payload.device_ids:
            try:
                device_id = uuid.UUID(raw)
            except ValueError:
                result.skipped += 1
                result.errors.append(f"{raw}: 无效设备 ID")
                continue
            if device_id in seen:
                continue
            seen.add(device_id)
            device = await self.device_repo.get_by_id_with_model(device_id)
            if not device:
                result.skipped += 1
                result.errors.append(f"{raw}: 设备不存在")
                continue
            if device.rack_id:
                result.skipped += 1
                result.errors.append(f"{device.hostname}: 已上架")
                continue
            queue.append(device_id)

        for item in payload.new_devices:
            try:
                async with self.session.begin_nested():
                    model = await self.model_repo.get_by_id(uuid.UUID(item.device_model_id))
                    if not model:
                        result.skipped += 1
                        result.errors.append(f"{item.serial_number}: 型号不存在")
                        continue
                    existing_sn = await self.device_repo.get_by_serial_including_deleted(
                        item.serial_number
                    )
                    if existing_sn and existing_sn.deleted_at is None:
                        result.skipped += 1
                        result.errors.append(f"{item.serial_number}: 序列号已存在")
                        continue
                    if existing_sn and existing_sn.deleted_at is not None:
                        await self.device_repo.free_unique_for_soft_deleted(existing_sn)

                    name = (item.name or item.hostname or item.serial_number).strip()
                    hostname = (item.hostname or name).strip()
                    existing_hn = await self.device_repo.get_by_hostname_including_deleted(
                        hostname
                    )
                    if existing_hn and existing_hn.deleted_at is None:
                        result.skipped += 1
                        result.errors.append(f"{hostname}: 主机名已存在")
                        continue
                    if existing_hn and existing_hn.deleted_at is not None:
                        await self.device_repo.free_unique_for_soft_deleted(existing_hn)

                    type_id = uuid.UUID(item.device_type_id) if item.device_type_id else None
                    manufacturer_id = None
                    if item.manufacturer_id:
                        mfg = await self.mfg_repo.get_by_id(uuid.UUID(item.manufacturer_id))
                        if not mfg:
                            raise ValidationError(
                                f"{item.serial_number}: 厂商不存在", code=10004
                            )
                        manufacturer_id = mfg.id
                    contract_id = None
                    if item.contract_id:
                        try:
                            cid = uuid.UUID(item.contract_id)
                        except ValueError as exc:
                            raise ValidationError(
                                f"{item.serial_number}: 无效合同 ID", code=10004
                            ) from exc
                        contract = await self.contract_repo.get_by_id(cid)
                        if not contract:
                            raise ValidationError(
                                f"{item.serial_number}: 采购合同不存在", code=10004
                            )
                        contract_id = contract.id
                    entity = Device(
                        name=name,
                        hostname=hostname,
                        serial_number=item.serial_number,
                        device_model_id=model.id,
                        device_type_id=type_id,
                        manufacturer_id=manufacturer_id,
                        contract_id=contract_id,
                        height_u=item.height_u or model.height_u,
                        power=item.power or model.power,
                        weight=model.weight,
                        status=DeviceStatus.STOCK.value,
                        description=item.description,
                        created_by=user_id,
                        updated_by=user_id,
                    )
                    created = await self.device_repo.create(entity)
                    result.created += 1
                    queue.append(created.id)
            except Exception as exc:  # noqa: BLE001
                result.skipped += 1
                result.errors.append(f"{item.serial_number}: {exc}")

        if not queue:
            return result

        async def _build_ip_queue(raw_ids: list[str], *, role: str) -> list:
            built: list = []
            if not raw_ids:
                return built
            try:
                wanted_ids = [uuid.UUID(x) for x in raw_ids]
            except ValueError as exc:
                raise ValidationError(f"存在无效{role} ID", code=10004) from exc
            ips = await self.ip_repo.list_by_ids(wanted_ids)
            ip_map = {i.id: i for i in ips}
            # 保持请求顺序，便于与设备 1:1 配对
            ordered = [ip_map[i] for i in wanted_ids if i in ip_map]
            for missing in [i for i in wanted_ids if i not in ip_map]:
                result.errors.append(f"{missing}: {role}不存在")
            for ip_entity in ordered:
                if getattr(ip_entity, "status", None) == IpStatus.DISABLED.value:
                    result.errors.append(f"{ip_entity.system_ip}: {role}已禁用，已跳过")
                    continue
                if ip_entity.device_id or getattr(ip_entity, "status", None) == IpStatus.ALLOCATED.value:
                    result.errors.append(f"{ip_entity.system_ip}: {role}已分配，已跳过")
                    continue
                built.append(ip_entity)
            return built

        business_queue = await _build_ip_queue(payload.ip_ids, role="业务IP")
        bmc_queue = await _build_ip_queue(payload.bmc_ip_ids, role="BMC地址")
        business_ids = {ip.id for ip in business_queue}
        overlap = [ip.system_ip for ip in bmc_queue if ip.id in business_ids]
        if overlap:
            raise ValidationError(
                f"业务IP与BMC地址不可重复：{', '.join(overlap[:5])}",
                code=10004,
            )

        room_id = uuid.UUID(payload.room_id)
        start_u = payload.start_u
        gap_u = payload.gap_u
        # 本批每柜最多上架台数（不含柜内历史已上架设备，避免 AA02 已有千兆时跳过空闲 U44）
        per_rack_limit = max(1, int(payload.per_rack_count or 1))

        # 每柜独立游标，轮询上架：先各柜落起始 U，再向下补齐
        rack_state: dict[uuid.UUID, dict] = {
            rack.id: {
                "rack": rack,
                "cursor_u": start_u,
                "mounted": 0,
                "attempted_us": set(),
                "exhausted": False,
            }
            for rack in racks
        }

        device_idx = 0
        while device_idx < len(queue):
            progressed = False
            for rack_id, st in rack_state.items():
                if device_idx >= len(queue):
                    break
                if st["exhausted"] or st["mounted"] >= per_rack_limit:
                    continue

                rack = st["rack"]
                device_id = queue[device_idx]
                device = await self.device_repo.get_by_id_with_model(device_id)
                if not device:
                    device_idx += 1
                    result.skipped += 1
                    result.errors.append(f"{device_id}: 设备不存在")
                    progressed = True
                    continue

                occupied_map = await self._build_occupied_map(rack.id)
                height = max(1, int(device.height_u or 1))
                cursor_u = st["cursor_u"]
                attempted_us: set[int] = st["attempted_us"]

                u_position = pick_mount_u(
                    total_u=rack.total_u,
                    height_u=height,
                    occupied_map=occupied_map,
                    start_u=cursor_u,
                    gap_u=0,
                    prefer_exact=True,
                )
                if u_position is None:
                    u_position = pick_mount_u(
                        total_u=rack.total_u,
                        height_u=height,
                        occupied_map=occupied_map,
                        start_u=cursor_u,
                        gap_u=gap_u,
                        prefer_exact=False,
                        direction="down",
                    )
                if u_position is None:
                    u_position = pick_mount_u(
                        total_u=rack.total_u,
                        height_u=height,
                        occupied_map=occupied_map,
                        start_u=cursor_u,
                        gap_u=gap_u,
                        prefer_exact=False,
                        direction="up",
                    )
                if u_position is None or u_position in attempted_us:
                    st["exhausted"] = True
                    continue
                attempted_us.add(u_position)

                try:
                    async with self.session.begin_nested():
                        await self.mount(
                            MountRequest(
                                device_id=str(device_id),
                                rack_id=str(rack.id),
                                u_position=u_position,
                            ),
                            user_id=user_id,
                        )
                        result.mounted += 1
                        st["mounted"] += 1
                        next_down = u_position - gap_u - height
                        st["cursor_u"] = (
                            next_down if next_down >= 1 else u_position + height + gap_u
                        )

                        assignment: dict = {
                            "device_id": str(device_id),
                            "hostname": device.hostname,
                            "rack_id": str(rack.id),
                            "rack_code": rack.code,
                            "u_position": u_position,
                            "system_ip": None,
                            "bmc_ip": None,
                            "ip_id": None,
                            "bmc_ip_id": None,
                        }

                        business_entity = business_queue.pop(0) if business_queue else None
                        bmc_entity = bmc_queue.pop(0) if bmc_queue else None

                        if business_entity:
                            business_entity.bind_type = IpBindType.DEVICE.value
                            business_entity.device_id = device_id
                            business_entity.rack_id = rack.id
                            business_entity.room_id = room_id
                            business_entity.u_position = u_position
                            business_entity.scope_rack_ids = None
                            business_entity.label = "business"
                            business_entity.status = IpStatus.ALLOCATED.value
                            business_entity.updated_by = user_id
                            business_entity.version += 1
                            result.ip_bound += 1
                            assignment["system_ip"] = business_entity.system_ip
                            assignment["ip_id"] = str(business_entity.id)

                        if bmc_entity:
                            bmc_entity.bind_type = IpBindType.DEVICE.value
                            bmc_entity.device_id = device_id
                            bmc_entity.rack_id = rack.id
                            bmc_entity.room_id = room_id
                            bmc_entity.u_position = u_position
                            bmc_entity.scope_rack_ids = None
                            bmc_entity.label = "bmc"
                            bmc_entity.status = IpStatus.ALLOCATED.value
                            bmc_entity.updated_by = user_id
                            bmc_entity.version += 1
                            result.ip_bound += 1
                            assignment["bmc_ip"] = bmc_entity.system_ip
                            assignment["bmc_ip_id"] = str(bmc_entity.id)
                            if business_entity:
                                business_entity.bmc_ip = bmc_entity.system_ip

                        result.assignments.append(assignment)
                    device_idx += 1
                    progressed = True
                except Exception as exc:  # noqa: BLE001
                    result.errors.append(f"{device.hostname}@{rack.code}/U{u_position}: {exc}")
                    st["cursor_u"] = max(1, u_position - 1)
                    progressed = True
                    # 同设备换 U 再试，不推进 device_idx
                    continue

            if not progressed:
                break

        # 剩余设备：已创建则保留库存不上架
        while device_idx < len(queue):
            leftover = await self.device_repo.get_by_id_with_model(queue[device_idx])
            label = leftover.hostname if leftover else str(queue[device_idx])
            result.stock_only += 1
            result.errors.append(
                f"{label}: 无可用机柜/U位或已达本批每柜上限，已创建并保留在库存（未上架）"
            )
            device_idx += 1

        if business_queue:
            result.errors.append(
                f"剩余 {len(business_queue)} 条业务IP未关联（无对应已上架设备）"
            )
        if bmc_queue:
            result.errors.append(
                f"剩余 {len(bmc_queue)} 条BMC地址未关联（无对应已上架设备）"
            )

        await self.session.flush()
        return result

    async def batch_unmount(
        self, payload: BatchUnmountRequest, user_id: uuid.UUID | None = None
    ) -> BatchUnmountResult:
        """批量下架：一次加载设备、按柜清位、一次释放 IP。"""
        result = BatchUnmountResult()
        seen: set[uuid.UUID] = set()
        requested: list[uuid.UUID] = []
        for raw in payload.device_ids:
            try:
                device_id = uuid.UUID(raw)
            except ValueError:
                result.skipped += 1
                result.errors.append(f"{raw}: 无效 ID")
                continue
            if device_id in seen:
                continue
            seen.add(device_id)
            requested.append(device_id)

        if not requested:
            return result

        devices = await self.device_repo.list_by_ids_with_relations(requested)
        by_id = {d.id: d for d in devices}
        to_unmount: list[Device] = []
        for device_id in requested:
            device = by_id.get(device_id)
            if not device:
                result.skipped += 1
                result.errors.append(f"{device_id}: 不存在")
                continue
            if not device.rack_id:
                result.skipped += 1
                result.errors.append(f"{device.hostname}: 未上架")
                continue
            to_unmount.append(device)

        if not to_unmount:
            return result

        # 按机柜批量清占用位
        by_rack: dict[uuid.UUID, list[Device]] = {}
        for device in to_unmount:
            assert device.rack_id is not None
            by_rack.setdefault(device.rack_id, []).append(device)

        for rack_id, group in by_rack.items():
            positions = await self.position_repo.list_by_rack(rack_id)
            device_ids = {d.id for d in group}
            for pos in positions:
                if pos.device_id in device_ids:
                    pos.occupied = False
                    pos.device_id = None
                    pos.updated_by = user_id

        for device in to_unmount:
            device.rack_id = None
            device.u_position = None
            device.status = DeviceStatus.STOCK.value
            device.updated_by = user_id
            device.version += 1
            result.unmounted += 1

        await self.ip_service.release_by_devices(
            [d.id for d in to_unmount], user_id=user_id
        )
        await self.session.flush()
        return result
