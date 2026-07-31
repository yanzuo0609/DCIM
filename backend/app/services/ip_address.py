import ipaddress
import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.ip_address import IpAddress, IpBindType, IpStatus
from app.repositories.device import DeviceRepository
from app.repositories.infrastructure import RoomRepository
from app.repositories.ip_address import IpAddressRepository
from app.repositories.rack import RackRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.ip_address import (
    IpAddressBatchCreateRequest,
    IpAddressBatchCreateResult,
    IpAddressCreate,
    IpAddressResponse,
    IpAddressUpdate,
    IpAllocateAssignment,
    IpAllocateRequest,
    IpAllocateResult,
    IpBatchDeleteRequest,
    IpBatchDeleteResult,
    IpBindBatchRequest,
    IpBindBatchResult,
    IpBindRequest,
    IpStatusBatchRequest,
    IpStatusBatchResult,
)


def _ip_sort_key(value: str) -> tuple:
    try:
        return (0, int(ipaddress.ip_address(value)))
    except ValueError:
        return (1, value)


def _iter_ipv4_range(start: str, end: str) -> list[str]:
    try:
        start_ip = ipaddress.ip_address(start)
        end_ip = ipaddress.ip_address(end)
    except ValueError as exc:
        raise ValidationError(f"无效 IP 地址: {exc}", code=10004) from exc
    if start_ip.version != end_ip.version:
        raise ValidationError("起止 IP 版本不一致", code=10004)
    if int(start_ip) > int(end_ip):
        raise ValidationError("起始 IP 不能大于结束 IP", code=10004)
    if int(end_ip) - int(start_ip) > 1024:
        raise ValidationError("单次最多生成 1024 个地址", code=10004)
    return [str(ipaddress.ip_address(i)) for i in range(int(start_ip), int(end_ip) + 1)]


class IpAddressService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = IpAddressRepository(session)
        self.device_repo = DeviceRepository(session)
        self.rack_repo = RackRepository(session)
        self.room_repo = RoomRepository(session)

    @staticmethod
    def _refresh_status(entity: IpAddress) -> None:
        """按绑定关系刷新状态；已禁用不自动改写。"""
        if entity.status == IpStatus.DISABLED.value:
            return
        if entity.device_id or entity.bind_type in (
            IpBindType.DEVICE.value,
            IpBindType.RACK.value,
            IpBindType.RACK_RANGE.value,
        ):
            entity.status = IpStatus.ALLOCATED.value
        else:
            entity.status = IpStatus.FREE.value

    def _to_response(self, entity: IpAddress) -> IpAddressResponse:
        device = entity.device
        rack = entity.rack
        room = entity.room
        scope = None
        if entity.scope_rack_ids:
            scope = [str(x) for x in entity.scope_rack_ids]
        return IpAddressResponse(
            id=str(entity.id),
            system_ip=entity.system_ip,
            bmc_ip=entity.bmc_ip,
            vip=entity.vip,
            netmask=entity.netmask,
            gateway=entity.gateway,
            dns=entity.dns,
            dns_secondary=entity.dns_secondary,
            label=entity.label,
            description=entity.description,
            status=entity.status or IpStatus.FREE.value,
            bind_type=entity.bind_type,
            device_id=str(entity.device_id) if entity.device_id else None,
            device_name=(device.name or device.hostname) if device else None,
            rack_id=str(entity.rack_id) if entity.rack_id else None,
            rack_code=rack.code if rack else None,
            room_id=str(entity.room_id) if entity.room_id else None,
            room_name=room.name if room else None,
            scope_rack_ids=scope,
            u_position=entity.u_position,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    async def list_ips(
        self,
        params: PaginationParams,
        *,
        room_id: uuid.UUID | None = None,
        rack_id: uuid.UUID | None = None,
        device_id: uuid.UUID | None = None,
        bind_type: str | None = None,
        status: str | None = None,
    ) -> tuple[list[IpAddressResponse], PaginationMeta]:
        filters: dict = {}
        if room_id:
            filters["room_id"] = room_id
        if rack_id:
            filters["rack_id"] = rack_id
        if device_id:
            filters["device_id"] = device_id
        if bind_type:
            filters["bind_type"] = bind_type
        if status:
            filters["status"] = status
        items, total = await self.repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort="system_ip",
            order="asc",
            filters=filters or None,
            search_fields=["system_ip", "bmc_ip", "vip", "label"],
        )
        fulls = await self.repo.list_by_ids([item.id for item in items])
        full_map = {f.id: f for f in fulls}
        enriched = [
            self._to_response(full_map[item.id]) for item in items if item.id in full_map
        ]
        # Keep IP numeric order even if DB sorts lexicographically
        enriched.sort(key=lambda x: _ip_sort_key(x.system_ip))
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return enriched, pagination

    async def create(self, payload: IpAddressCreate, user_id: uuid.UUID | None = None) -> IpAddressResponse:
        if await self.repo.get_by_system_ip(payload.system_ip):
            raise ConflictError("系统 IP 已存在")
        initial_status = payload.status or IpStatus.FREE.value
        if initial_status not in {s.value for s in IpStatus}:
            raise ValidationError("无效地址状态", code=10004)
        entity = IpAddress(
            system_ip=payload.system_ip.strip(),
            bmc_ip=payload.bmc_ip.strip() if payload.bmc_ip else None,
            vip=payload.vip.strip() if payload.vip else None,
            netmask=payload.netmask.strip() if payload.netmask else None,
            gateway=payload.gateway.strip() if payload.gateway else None,
            dns=payload.dns.strip() if payload.dns else None,
            dns_secondary=payload.dns_secondary.strip() if payload.dns_secondary else None,
            label=payload.label,
            description=payload.description,
            status=initial_status,
            bind_type=IpBindType.NONE.value,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        full = await self.repo.get_by_id_full(created.id)
        assert full is not None
        return self._to_response(full)

    async def update(
        self, entity_id: uuid.UUID, payload: IpAddressUpdate, user_id: uuid.UUID | None = None
    ) -> IpAddressResponse:
        entity = await self.repo.get_by_id_full(entity_id)
        if not entity:
            raise NotFoundError("IP 记录不存在")
        if payload.system_ip and payload.system_ip != entity.system_ip:
            if await self.repo.get_by_system_ip(payload.system_ip):
                raise ConflictError("系统 IP 已存在")
            entity.system_ip = payload.system_ip.strip()
        if payload.bmc_ip is not None:
            entity.bmc_ip = payload.bmc_ip.strip() or None
        if payload.vip is not None:
            entity.vip = payload.vip.strip() or None
        if payload.netmask is not None:
            entity.netmask = payload.netmask.strip() or None
        if payload.gateway is not None:
            entity.gateway = payload.gateway.strip() or None
        if payload.dns is not None:
            entity.dns = payload.dns.strip() or None
        if payload.dns_secondary is not None:
            entity.dns_secondary = payload.dns_secondary.strip() or None
        if payload.label is not None:
            entity.label = payload.label
        if payload.description is not None:
            entity.description = payload.description
        if payload.status is not None:
            await self._set_status(entity, payload.status, user_id)
        else:
            entity.updated_by = user_id
            entity.version += 1
        await self.session.flush()
        full = await self.repo.get_by_id_full(entity_id)
        assert full is not None
        return self._to_response(full)

    async def _set_status(
        self, entity: IpAddress, status: str, user_id: uuid.UUID | None
    ) -> None:
        if status not in {s.value for s in IpStatus}:
            raise ValidationError("无效地址状态", code=10004)
        if status == IpStatus.DISABLED.value:
            entity.status = IpStatus.DISABLED.value
        elif status == IpStatus.FREE.value:
            entity.status = IpStatus.FREE.value
            self._refresh_status(entity)
        else:
            entity.status = IpStatus.ALLOCATED.value
            if not (
                entity.device_id
                or entity.bind_type
                in (
                    IpBindType.DEVICE.value,
                    IpBindType.RACK.value,
                    IpBindType.RACK_RANGE.value,
                )
            ):
                entity.status = IpStatus.FREE.value
        entity.updated_by = user_id
        entity.version += 1

    async def set_status_batch(
        self, payload: IpStatusBatchRequest, user_id: uuid.UUID | None = None
    ) -> IpStatusBatchResult:
        result = IpStatusBatchResult()
        for raw in payload.ids:
            try:
                entity_id = uuid.UUID(raw)
            except ValueError:
                result.skipped += 1
                result.errors.append(f"{raw}: 无效 ID")
                continue
            entity = await self.repo.get_by_id(entity_id)
            if not entity:
                result.skipped += 1
                result.errors.append(f"{raw}: 不存在")
                continue
            try:
                await self._set_status(entity, payload.status, user_id)
                result.updated += 1
            except Exception as exc:  # noqa: BLE001
                result.skipped += 1
                result.errors.append(f"{entity.system_ip}: {exc}")
        await self.session.flush()
        return result

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("IP 记录不存在")
        await self.repo.soft_delete(entity, deleted_by=user_id)

    async def batch_delete(
        self, payload: IpBatchDeleteRequest, user_id: uuid.UUID | None = None
    ) -> IpBatchDeleteResult:
        result = IpBatchDeleteResult()
        for raw in payload.ids:
            try:
                entity_id = uuid.UUID(raw)
            except ValueError:
                result.skipped += 1
                result.errors.append(f"{raw}: 无效 ID")
                continue
            entity = await self.repo.get_by_id(entity_id)
            if not entity:
                result.skipped += 1
                result.errors.append(f"{raw}: 不存在")
                continue
            await self.repo.soft_delete(entity, deleted_by=user_id)
            result.deleted += 1
        await self.session.flush()
        return result

    async def batch_create(
        self, payload: IpAddressBatchCreateRequest, user_id: uuid.UUID | None = None
    ) -> IpAddressBatchCreateResult:
        system_ips = _iter_ipv4_range(
            payload.start_system_ip.strip(), payload.end_system_ip.strip()
        )
        bmc_ips: list[str | None] = [None] * len(system_ips)
        if payload.start_bmc_ip and payload.start_bmc_ip.strip():
            try:
                start_bmc = ipaddress.ip_address(payload.start_bmc_ip.strip())
            except ValueError as exc:
                raise ValidationError(f"无效 BMC 起始 IP: {exc}", code=10004) from exc
            bmc_ips = [str(ipaddress.ip_address(int(start_bmc) + i)) for i in range(len(system_ips))]

        if payload.gateway and payload.gateway.strip():
            try:
                ipaddress.ip_address(payload.gateway.strip())
            except ValueError as exc:
                raise ValidationError(f"无效网关地址: {exc}", code=10004) from exc
        for dns_val, label in (
            (payload.dns, "DNS"),
            (payload.dns_secondary, "备用 DNS"),
        ):
            if dns_val and dns_val.strip():
                try:
                    ipaddress.ip_address(dns_val.strip())
                except ValueError as exc:
                    raise ValidationError(f"无效{label}: {exc}", code=10004) from exc

        netmask = payload.netmask.strip() if payload.netmask else None
        gateway = payload.gateway.strip() if payload.gateway else None
        dns = payload.dns.strip() if payload.dns else None
        dns_secondary = payload.dns_secondary.strip() if payload.dns_secondary else None

        result = IpAddressBatchCreateResult()
        for idx, system_ip in enumerate(system_ips):
            if await self.repo.get_by_system_ip(system_ip):
                result.skipped += 1
                result.errors.append(f"{system_ip}: 已存在")
                continue
            label = None
            if payload.label_prefix:
                label = f"{payload.label_prefix}-{idx + 1}"
            entity = IpAddress(
                system_ip=system_ip,
                bmc_ip=bmc_ips[idx],
                vip=None,
                netmask=netmask,
                gateway=gateway,
                dns=dns,
                dns_secondary=dns_secondary,
                label=label,
                description=payload.description,
                status=IpStatus.FREE.value,
                bind_type=IpBindType.NONE.value,
                created_by=user_id,
                updated_by=user_id,
            )
            await self.repo.create(entity)
            result.created += 1
        await self.session.flush()
        return result

    async def _apply_bind(
        self, entity: IpAddress, bind: IpBindRequest, user_id: uuid.UUID | None
    ) -> None:
        if (
            entity.status == IpStatus.DISABLED.value
            and bind.bind_type != "none"
        ):
            raise ValidationError("已禁用的 IP 不可分配，请先启用", code=10004)
        if bind.bind_type == "none":
            entity.bind_type = IpBindType.NONE.value
            entity.device_id = None
            entity.rack_id = None
            entity.room_id = None
            entity.scope_rack_ids = None
            entity.u_position = None
        elif bind.bind_type == "device":
            if not bind.device_id:
                raise ValidationError("请指定设备", code=10004)
            device = await self.device_repo.get_by_id_with_model(uuid.UUID(bind.device_id))
            if not device:
                raise NotFoundError("设备不存在")
            entity.bind_type = IpBindType.DEVICE.value
            entity.device_id = device.id
            entity.rack_id = device.rack_id
            entity.u_position = device.u_position
            entity.scope_rack_ids = None
            if device.rack_id:
                rack = await self.rack_repo.get_by_id(device.rack_id)
                entity.room_id = rack.room_id if rack else None
            else:
                entity.room_id = None
        elif bind.bind_type == "rack":
            if not bind.rack_id:
                raise ValidationError("请指定机柜", code=10004)
            rack = await self.rack_repo.get_by_id(uuid.UUID(bind.rack_id))
            if not rack:
                raise NotFoundError("机柜不存在")
            entity.bind_type = IpBindType.RACK.value
            entity.rack_id = rack.id
            entity.room_id = rack.room_id
            entity.device_id = None
            entity.u_position = None
            entity.scope_rack_ids = None
        elif bind.bind_type == "rack_range":
            if not bind.room_id:
                raise ValidationError("请指定机房", code=10004)
            room = await self.room_repo.get_by_id(uuid.UUID(bind.room_id))
            if not room:
                raise NotFoundError("机房不存在")
            rack_ids = [uuid.UUID(x) for x in bind.rack_ids] if bind.rack_ids else []
            if not rack_ids:
                racks = await self.rack_repo.list_by_room(room.id)
                rack_ids = [r.id for r in racks]
            if not rack_ids:
                raise ValidationError("机柜范围为空", code=10004)
            entity.bind_type = IpBindType.RACK_RANGE.value
            entity.room_id = room.id
            entity.rack_id = None
            entity.device_id = None
            entity.u_position = None
            entity.scope_rack_ids = [str(x) for x in rack_ids]
        else:
            raise ValidationError("无效关联类型", code=10004)
        self._refresh_status(entity)
        entity.updated_by = user_id
        entity.version += 1

    async def bind_one(
        self, entity_id: uuid.UUID, bind: IpBindRequest, user_id: uuid.UUID | None = None
    ) -> IpAddressResponse:
        entity = await self.repo.get_by_id_full(entity_id)
        if not entity:
            raise NotFoundError("IP 记录不存在")
        await self._apply_bind(entity, bind, user_id)
        await self.session.flush()
        full = await self.repo.get_by_id_full(entity_id)
        assert full is not None
        return self._to_response(full)

    async def bind_batch(
        self, payload: IpBindBatchRequest, user_id: uuid.UUID | None = None
    ) -> IpBindBatchResult:
        result = IpBindBatchResult()
        for raw in payload.ids:
            try:
                entity_id = uuid.UUID(raw)
            except ValueError:
                result.skipped += 1
                result.errors.append(f"{raw}: 无效 ID")
                continue
            entity = await self.repo.get_by_id(entity_id)
            if not entity:
                result.skipped += 1
                result.errors.append(f"{raw}: 不存在")
                continue
            try:
                await self._apply_bind(entity, payload.bind, user_id)
                result.updated += 1
            except Exception as exc:  # noqa: BLE001
                result.skipped += 1
                result.errors.append(f"{entity.system_ip}: {exc}")
        await self.session.flush()
        return result

    async def allocate(
        self, payload: IpAllocateRequest, user_id: uuid.UUID | None = None
    ) -> IpAllocateResult:
        """按系统 IP 升序，机柜编号升序、低 U 位设备分配；设备间至少间隔 1U。"""
        result = IpAllocateResult()
        room_id = uuid.UUID(payload.room_id)
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("机房不存在")

        try:
            ip_ids = [uuid.UUID(x) for x in payload.ip_ids]
        except ValueError as exc:
            raise ValidationError("存在无效 IP ID", code=10004) from exc

        ips = await self.repo.list_by_ids(ip_ids)
        ip_map = {i.id: i for i in ips}
        ordered_ips = sorted(
            [ip_map[i] for i in ip_ids if i in ip_map],
            key=lambda x: _ip_sort_key(x.system_ip),
        )
        for missing in [i for i in ip_ids if i not in ip_map]:
            result.skipped += 1
            result.errors.append(f"{missing}: IP 不存在")

        racks = await self.rack_repo.list_by_room(room_id)
        if payload.rack_ids:
            wanted = {uuid.UUID(x) for x in payload.rack_ids}
            racks = [r for r in racks if r.id in wanted]
        if payload.row_nos:
            rows = set(payload.row_nos)
            racks = [r for r in racks if r.row_no in rows]
        if payload.column_nos:
            cols = set(payload.column_nos)
            racks = [r for r in racks if r.column_no in cols]
        racks.sort(key=lambda r: (r.code, r.row_no, r.column_no))

        if not racks:
            raise ValidationError("未找到可用机柜", code=10004)

        # Collect mounted devices: rack code ASC, u ASC
        candidates = []
        for rack in racks:
            devices = await self.device_repo.list_by_rack(rack.id)
            for device in devices:
                if device.u_position is None:
                    continue
                candidates.append((rack, device))
        candidates.sort(key=lambda x: (x[0].code, x[1].u_position or 0))

        # Filter with 1U gap between consecutive selected devices
        selected: list[tuple] = []
        prev_end: int | None = None
        prev_rack_id: uuid.UUID | None = None
        for rack, device in candidates:
            start = device.u_position or 1
            end = start + device.height_u - 1
            if prev_end is not None and rack.id == prev_rack_id:
                # need at least 1 empty U between devices
                if start < prev_end + 2:
                    continue
            selected.append((rack, device))
            prev_end = end
            prev_rack_id = rack.id

        if not selected:
            raise ValidationError("机柜范围内无可分配的已上架设备（或无法满足 1U 间隔）", code=10004)

        device_idx = 0
        for ip_entity in ordered_ips:
            if ip_entity.status == IpStatus.DISABLED.value:
                result.skipped += 1
                result.errors.append(f"{ip_entity.system_ip}: 已禁用")
                continue
            if ip_entity.device_id or ip_entity.status == IpStatus.ALLOCATED.value:
                result.skipped += 1
                result.errors.append(f"{ip_entity.system_ip}: 已分配")
                continue
            if device_idx >= len(selected):
                result.skipped += 1
                result.errors.append(f"{ip_entity.system_ip}: 可用设备不足")
                continue
            rack, device = selected[device_idx]
            device_idx += 1
            ip_entity.bind_type = IpBindType.DEVICE.value
            ip_entity.device_id = device.id
            ip_entity.rack_id = rack.id
            ip_entity.room_id = room_id
            ip_entity.u_position = device.u_position
            ip_entity.scope_rack_ids = None
            ip_entity.status = IpStatus.ALLOCATED.value
            ip_entity.updated_by = user_id
            ip_entity.version += 1
            result.allocated += 1
            result.assignments.append(
                IpAllocateAssignment(
                    ip_id=str(ip_entity.id),
                    system_ip=ip_entity.system_ip,
                    device_id=str(device.id),
                    device_name=device.name or device.hostname,
                    rack_id=str(rack.id),
                    rack_code=rack.code,
                    u_position=device.u_position or 0,
                )
            )

        await self.session.flush()
        return result
