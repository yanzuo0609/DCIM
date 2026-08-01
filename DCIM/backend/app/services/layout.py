import ipaddress
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.layout.engine import find_first_available, occupied_range, validate_mount
from app.models.device import Device, DeviceStatus
from app.models.ip_address import IpBindType, IpStatus
from app.repositories.device import DeviceModelRepository, DeviceRepository
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
        self.room_repo = RoomRepository(session)
        self.ip_repo = IpAddressRepository(session)
        self.ip_service = IpAddressService(session)

    async def _build_occupied_map(self, rack_id: uuid.UUID) -> dict[int, uuid.UUID | None]:
        positions = await self.position_repo.list_by_rack(rack_id)
        return {pos.u_position: pos.device_id for pos in positions if pos.occupied}

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
                model = await self.model_repo.get_by_id(uuid.UUID(item.device_model_id))
                if not model:
                    result.skipped += 1
                    result.errors.append(f"{item.serial_number}: 型号不存在")
                    continue
                if await self.device_repo.get_by_serial(item.serial_number):
                    result.skipped += 1
                    result.errors.append(f"{item.serial_number}: 序列号已存在")
                    continue
                name = (item.name or item.hostname or item.serial_number).strip()
                hostname = (item.hostname or name).strip()
                if await self.device_repo.get_by_hostname(hostname):
                    result.skipped += 1
                    result.errors.append(f"{hostname}: 主机名已存在")
                    continue
                type_id = uuid.UUID(item.device_type_id) if item.device_type_id else None
                entity = Device(
                    name=name,
                    hostname=hostname,
                    serial_number=item.serial_number,
                    device_model_id=model.id,
                    device_type_id=type_id,
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

        ip_queue: list = []
        if payload.ip_ids:
            try:
                wanted_ids = [uuid.UUID(x) for x in payload.ip_ids]
            except ValueError as exc:
                raise ValidationError("存在无效 IP ID", code=10004) from exc
            ips = await self.ip_repo.list_by_ids(wanted_ids)
            ip_map = {i.id: i for i in ips}
            ordered = sorted(
                [ip_map[i] for i in wanted_ids if i in ip_map],
                key=lambda x: _ip_sort_key(x.system_ip),
            )
            for missing in [i for i in wanted_ids if i not in ip_map]:
                result.errors.append(f"{missing}: IP 不存在")
            for ip_entity in ordered:
                if getattr(ip_entity, "status", None) == IpStatus.DISABLED.value:
                    result.errors.append(f"{ip_entity.system_ip}: IP 已禁用，已跳过")
                    continue
                if ip_entity.device_id or getattr(ip_entity, "status", None) == IpStatus.ALLOCATED.value:
                    result.errors.append(f"{ip_entity.system_ip}: IP 已分配，已跳过")
                    continue
                ip_queue.append(ip_entity)

        room_id = uuid.UUID(payload.room_id)
        start_u = payload.start_u
        gap_u = payload.gap_u

        device_idx = 0
        for rack in racks:
            if device_idx >= len(queue):
                break
            mounted_in_rack = 0
            cursor_u = start_u
            while mounted_in_rack < payload.per_rack_count and device_idx < len(queue):
                device_id = queue[device_idx]
                device = await self.device_repo.get_by_id_with_model(device_id)
                if not device:
                    device_idx += 1
                    result.skipped += 1
                    result.errors.append(f"{device_id}: 设备不存在")
                    continue
                occupied_map = await self._build_occupied_map(rack.id)
                u_position = find_first_available(
                    total_u=rack.total_u,
                    height_u=device.height_u,
                    occupied_map=occupied_map,
                    start_u=cursor_u,
                    gap_u=gap_u,
                )
                if u_position is None:
                    break
                try:
                    await self.mount(
                        MountRequest(
                            device_id=str(device_id),
                            rack_id=str(rack.id),
                            u_position=u_position,
                        ),
                        user_id=user_id,
                    )
                    result.mounted += 1
                    mounted_in_rack += 1
                    cursor_u = u_position + device.height_u + gap_u

                    assignment: dict = {
                        "device_id": str(device_id),
                        "hostname": device.hostname,
                        "rack_id": str(rack.id),
                        "rack_code": rack.code,
                        "u_position": u_position,
                        "system_ip": None,
                        "ip_id": None,
                    }

                    if ip_queue:
                        ip_entity = ip_queue.pop(0)
                        ip_entity.bind_type = IpBindType.DEVICE.value
                        ip_entity.device_id = device_id
                        ip_entity.rack_id = rack.id
                        ip_entity.room_id = room_id
                        ip_entity.u_position = u_position
                        ip_entity.scope_rack_ids = None
                        ip_entity.status = IpStatus.ALLOCATED.value
                        ip_entity.updated_by = user_id
                        ip_entity.version += 1
                        result.ip_bound += 1
                        assignment["system_ip"] = ip_entity.system_ip
                        assignment["ip_id"] = str(ip_entity.id)

                    result.assignments.append(assignment)
                except Exception as exc:  # noqa: BLE001
                    result.skipped += 1
                    result.errors.append(f"{device.hostname}: {exc}")
                device_idx += 1

        while device_idx < len(queue):
            leftover = await self.device_repo.get_by_id_with_model(queue[device_idx])
            label = leftover.hostname if leftover else str(queue[device_idx])
            result.skipped += 1
            result.errors.append(f"{label}: 机柜空间不足，未能上架")
            device_idx += 1

        if ip_queue:
            result.errors.append(f"剩余 {len(ip_queue)} 条 IP 未关联（设备已全部上架或不足）")

        await self.session.flush()
        return result

    async def batch_unmount(
        self, payload: BatchUnmountRequest, user_id: uuid.UUID | None = None
    ) -> BatchUnmountResult:
        result = BatchUnmountResult()
        seen: set[uuid.UUID] = set()
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
            device = await self.device_repo.get_by_id_with_model(device_id)
            if not device:
                result.skipped += 1
                result.errors.append(f"{raw}: 不存在")
                continue
            if not device.rack_id:
                result.skipped += 1
                result.errors.append(f"{device.hostname}: 未上架")
                continue
            try:
                await self.unmount(UnmountRequest(device_id=str(device_id)), user_id=user_id)
                result.unmounted += 1
            except Exception as exc:  # noqa: BLE001
                result.skipped += 1
                result.errors.append(f"{device.hostname}: {exc}")
        return result
