import ipaddress
import math
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.device import Device
from app.models.ip_address import IpAddress, IpBindType, IpSegment, IpStatus
from app.repositories.device import DeviceRepository
from app.repositories.infrastructure import RoomRepository
from app.repositories.ip_address import IpAddressRepository, IpSegmentRepository
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
    IpSegmentCreate,
    IpSegmentDetail,
    IpSegmentResponse,
    IpSegmentUpdate,
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


def _expand_cidr(network: str, prefix_len: int | None = None) -> tuple[ipaddress.IPv4Network, list[str]]:
    raw = (network or "").strip()
    if not raw:
        raise ValidationError("请填写 IP 地址段", code=10004)
    try:
        if "/" in raw:
            net = ipaddress.ip_network(raw, strict=False)
            if prefix_len is not None and int(prefix_len) != net.prefixlen:
                # 掩码位数与地址段内 /xx 不一致时，以显式位数为准
                net = ipaddress.ip_network(f"{net.network_address}/{int(prefix_len)}", strict=False)
        else:
            if prefix_len is None:
                raise ValidationError("请填写掩码位数", code=10004)
            net = ipaddress.ip_network(f"{raw}/{int(prefix_len)}", strict=False)
    except ValueError as exc:
        raise ValidationError(f"无效地址段或掩码: {exc}", code=10004) from exc
    if not isinstance(net, ipaddress.IPv4Network):
        raise ValidationError("仅支持 IPv4 地址段", code=10004)
    hosts = [str(h) for h in net.hosts()]
    if len(hosts) > 1024:
        raise ValidationError("单次最多生成 1024 个可用主机地址（掩码过小）", code=10004)
    if not hosts:
        raise ValidationError("该掩码下没有可用主机地址", code=10004)
    return net, hosts


def _parse_reserved_ips(
    reserved_ips: str | list[str] | None,
    *,
    reserved_count: int | None,
    hosts: list[str],
) -> set[str]:
    """解析保留地址：支持单个 IP、逗号/空格/换行分隔，或起止范围 a-b。"""
    host_set = set(hosts)
    reserved: set[str] = set()

    tokens: list[str] = []
    if isinstance(reserved_ips, list):
        tokens = [str(x).strip() for x in reserved_ips if str(x).strip()]
    elif isinstance(reserved_ips, str) and reserved_ips.strip():
        for part in reserved_ips.replace(";", ",").replace("\n", ",").replace(" ", ",").split(","):
            token = part.strip()
            if token:
                tokens.append(token)

    for token in tokens:
        if "-" in token and token.count("-") == 1 and not token.startswith("-"):
            start_s, end_s = [x.strip() for x in token.split("-", 1)]
            try:
                for ip in _iter_ipv4_range(start_s, end_s):
                    if ip not in host_set:
                        raise ValidationError(f"保留地址 {ip} 不在该地址段内", code=10004)
                    reserved.add(ip)
            except ValidationError:
                raise
            except Exception as exc:
                raise ValidationError(f"无效保留地址范围: {token}", code=10004) from exc
        else:
            try:
                ip = str(ipaddress.ip_address(token))
            except ValueError as exc:
                raise ValidationError(f"无效保留地址: {token}", code=10004) from exc
            if ip not in host_set:
                raise ValidationError(f"保留地址 {ip} 不在该地址段内", code=10004)
            reserved.add(ip)

    if not reserved and reserved_count:
        count = int(reserved_count)
        if count < 0:
            raise ValidationError("保留个数不能为负数", code=10004)
        if count > len(hosts):
            raise ValidationError("保留个数不能大于可用主机数", code=10004)
        # 兼容旧接口：从段尾保留 N 个
        reserved = set(hosts[-count:]) if count else set()

    return reserved


def _prefix_to_dotted(prefix_len: int) -> str:
    return str(ipaddress.IPv4Network(f"0.0.0.0/{prefix_len}").netmask)


def _guess_prefix(netmask: str | None) -> int:
    if not netmask:
        return 24
    raw = netmask.strip().lstrip("/")
    if raw.isdigit():
        return int(raw)
    try:
        return ipaddress.IPv4Network(f"0.0.0.0/{raw}").prefixlen
    except ValueError:
        return 24


class IpAddressService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.repo = IpAddressRepository(session)
        self.segment_repo = IpSegmentRepository(session)
        self.device_repo = DeviceRepository(session)
        self.rack_repo = RackRepository(session)
        self.room_repo = RoomRepository(session)

    @staticmethod
    def _refresh_status(entity: IpAddress) -> None:
        """按绑定关系刷新状态；已禁用/保留不自动改写。"""
        if entity.status in {IpStatus.DISABLED.value, IpStatus.RESERVED.value}:
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
        # 软删设备不展示为有效分配
        if device is not None and getattr(device, "deleted_at", None) is not None:
            device = None
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
            segment_id=str(entity.segment_id) if entity.segment_id else None,
            bind_type=entity.bind_type if device or entity.bind_type != IpBindType.DEVICE.value else IpBindType.NONE.value,
            device_id=str(entity.device_id) if entity.device_id and device else None,
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

    def _clear_device_bind(self, entity: IpAddress, user_id: uuid.UUID | None) -> None:
        entity.bind_type = IpBindType.NONE.value
        entity.device_id = None
        entity.rack_id = None
        entity.room_id = None
        entity.scope_rack_ids = None
        entity.u_position = None
        # 释放设备角色绑定时清掉业务/带外/VIP 标记
        if (entity.label or "") in {"bmc", "business", "vip"} or entity.bmc_ip or entity.vip:
            entity.bmc_ip = None
            entity.vip = None
            entity.label = None
        self._refresh_status(entity)
        entity.updated_by = user_id
        entity.version += 1

    async def reconcile_stale_device_binds(
        self,
        *,
        segment_id: uuid.UUID | None = None,
        user_id: uuid.UUID | None = None,
    ) -> int:
        """释放已删除设备上残留的 IP 绑定（库存设备可保留已分配 IP）。"""
        ips = await self.repo.list_device_bound(segment_id=segment_id)
        if not ips:
            return 0
        device_ids = list({ip.device_id for ip in ips if ip.device_id})
        if not device_ids:
            return 0
        stmt = select(Device).where(Device.id.in_(device_ids))
        devices = list((await self.session.execute(stmt)).scalars().all())
        device_map = {d.id: d for d in devices}

        released = 0
        for entity in ips:
            device = device_map.get(entity.device_id) if entity.device_id else None
            should_release = device is None or device.deleted_at is not None
            if not should_release:
                continue
            self._clear_device_bind(entity, user_id)
            released += 1
        if released:
            await self.session.flush()
        return released

    async def assign_device_ips(
        self,
        device_id: uuid.UUID,
        *,
        system_ip_id: str | None = None,
        bmc_ip_id: str | None = None,
        vip_ip_id: str | None = None,
        user_id: uuid.UUID | None = None,
        replace_existing: bool = False,
    ) -> None:
        """为设备分配业务 / 带外 / 虚拟 IP。

        - 业务、带外：仅允许空闲地址，独占绑定到设备
        - 虚拟 IP：可选任意非禁用地址，且不独占，多台设备可共用同一 VIP
        """
        device = await self.device_repo.get_by_id_with_model(device_id)
        if not device:
            raise NotFoundError("设备不存在")

        if replace_existing:
            await self.release_by_device(device_id, user_id=user_id)

        async def _load(raw: str | None, *, role: str) -> IpAddress | None:
            if raw is None or raw == "":
                return None
            try:
                entity_id = uuid.UUID(raw)
            except ValueError as exc:
                raise ValidationError(f"无效{role} ID", code=10004) from exc
            entity = await self.repo.get_by_id_full(entity_id)
            if not entity:
                raise NotFoundError(f"{role} 不存在")
            return entity

        system_entity = await _load(system_ip_id, role="业务IP")
        bmc_entity = await _load(bmc_ip_id, role="带外管理IP")
        vip_entity = await _load(vip_ip_id, role="虚拟IP")

        if system_entity:
            if system_entity.status == IpStatus.DISABLED.value:
                raise ValidationError("已禁用的业务IP不可分配", code=10004)
            if system_entity.status not in {IpStatus.FREE.value, IpStatus.RESERVED.value}:
                if not (
                    system_entity.device_id == device_id
                    and system_entity.status == IpStatus.ALLOCATED.value
                ):
                    raise ValidationError(
                        f"业务IP {system_entity.system_ip} 已被占用", code=10004
                    )
            await self._apply_bind(
                system_entity,
                IpBindRequest(bind_type="device", device_id=str(device_id)),
                user_id,
            )
            system_entity.label = "business"
            system_entity.status = IpStatus.ALLOCATED.value

        if bmc_entity:
            if system_entity and bmc_entity.id == system_entity.id:
                raise ValidationError("带外管理IP不能与业务IP相同", code=10004)
            if bmc_entity.status == IpStatus.DISABLED.value:
                raise ValidationError("已禁用的带外管理IP不可分配", code=10004)
            if bmc_entity.status not in {IpStatus.FREE.value, IpStatus.RESERVED.value}:
                if not (
                    bmc_entity.device_id == device_id
                    and bmc_entity.status == IpStatus.ALLOCATED.value
                ):
                    raise ValidationError(
                        f"带外管理IP {bmc_entity.system_ip} 已被占用", code=10004
                    )
            await self._apply_bind(
                bmc_entity,
                IpBindRequest(bind_type="device", device_id=str(device_id)),
                user_id,
            )
            bmc_entity.label = "bmc"
            bmc_entity.status = IpStatus.ALLOCATED.value
            if system_entity:
                system_entity.bmc_ip = bmc_entity.system_ip

        if vip_entity:
            if vip_entity.status == IpStatus.DISABLED.value:
                raise ValidationError("已禁用的虚拟IP不可分配", code=10004)
            target = system_entity or bmc_entity
            if target is None:
                raise ValidationError(
                    "分配虚拟IP前请先分配业务地址或带外地址", code=10004
                )
            # 不修改 vip_entity 的绑定/状态，允许多台设备共用
            target.vip = vip_entity.system_ip

        await self.session.flush()

    async def _segment_counts(self, segment_id: uuid.UUID) -> dict[str, int]:
        return await self.repo.count_by_segment_status(segment_id)

    def _to_segment_response(
        self, segment: IpSegment, counts: dict[str, int] | None = None
    ) -> IpSegmentResponse:
        counts = counts or {}
        network = segment.network or segment.start_ip
        prefix_len = segment.prefix_len or _guess_prefix(segment.netmask)
        purpose = segment.address_purpose or segment.application_type
        remarks = segment.remarks if segment.remarks is not None else segment.description
        return IpSegmentResponse(
            id=str(segment.id),
            application=segment.application,
            network=network,
            prefix_len=prefix_len,
            gateway=segment.gateway,
            address_purpose=purpose,
            network_type=segment.network_type,
            location=segment.location,
            remarks=remarks,
            total_count=int(counts.get("total", 0)),
            free_count=int(counts.get(IpStatus.FREE.value, 0)),
            allocated_count=int(counts.get(IpStatus.ALLOCATED.value, 0)),
            reserved_count=int(counts.get(IpStatus.RESERVED.value, 0)),
            disabled_count=int(counts.get(IpStatus.DISABLED.value, 0)),
            name=segment.name,
            start_ip=segment.start_ip,
            end_ip=segment.end_ip,
            netmask=segment.netmask or str(prefix_len),
            dns=segment.dns,
            dns_secondary=segment.dns_secondary,
            application_type=purpose,
            label=segment.label,
            description=remarks,
            created_at=segment.created_at,
            updated_at=segment.updated_at,
        )

    async def _normalize_segments(self) -> None:
        """补齐旧地址段的 network/prefix/用途等字段。"""
        segments = await self.segment_repo.list_all_active()
        dirty = False
        for segment in segments:
            changed = False
            if not segment.network:
                segment.network = segment.start_ip
                changed = True
            if not segment.prefix_len:
                segment.prefix_len = _guess_prefix(segment.netmask)
                changed = True
            if not segment.address_purpose and segment.application_type:
                segment.address_purpose = segment.application_type
                changed = True
            if segment.remarks is None and segment.description:
                segment.remarks = segment.description
                changed = True
            if not segment.netmask:
                segment.netmask = str(segment.prefix_len or 24)
                changed = True
            if changed:
                dirty = True
        if dirty:
            await self.session.flush()

    async def _backfill_orphan_segments(self, user_id: uuid.UUID | None = None) -> None:
        """将历史未归属地址按网关/掩码/标签归入地址段。"""
        orphans = await self.repo.list_orphans()
        if not orphans:
            return
        orphans.sort(key=lambda x: _ip_sort_key(x.system_ip))
        groups: dict[tuple[str, str, str], list[IpAddress]] = {}
        for ip in orphans:
            key = (ip.gateway or "", ip.netmask or "", ip.label or "")
            groups.setdefault(key, []).append(ip)
        for (gateway, netmask, label), items in groups.items():
            items.sort(key=lambda x: _ip_sort_key(x.system_ip))
            start_ip = items[0].system_ip
            end_ip = items[-1].system_ip
            prefix = _guess_prefix(netmask)
            try:
                net = ipaddress.ip_network(f"{start_ip}/{prefix}", strict=False)
                network = str(net.network_address)
            except ValueError:
                network = start_ip
            name = label or f"{network}/{prefix}"
            segment = IpSegment(
                application=None,
                network=network,
                prefix_len=prefix,
                gateway=gateway or None,
                address_purpose=None,
                network_type=None,
                location=None,
                remarks=items[0].description,
                name=name[:100],
                start_ip=start_ip,
                end_ip=end_ip,
                netmask=str(prefix),
                dns=items[0].dns,
                dns_secondary=items[0].dns_secondary,
                application_type=None,
                label=label or None,
                description=items[0].description,
                created_by=user_id,
                updated_by=user_id,
            )
            created = await self.segment_repo.create(segment)
            for ip in items:
                ip.segment_id = created.id
        await self.session.flush()

    async def list_segments(
        self,
        params: PaginationParams,
        *,
        application_type: str | None = None,
        address_purpose: str | None = None,
        application: str | None = None,
    ) -> tuple[list[IpSegmentResponse], PaginationMeta]:
        await self._backfill_orphan_segments()
        await self._normalize_segments()
        await self.reconcile_stale_device_binds()
        filters: dict = {}
        if application_type:
            filters["address_purpose"] = application_type
        if address_purpose:
            filters["address_purpose"] = address_purpose
        if application:
            filters["application"] = application
        items, total = await self.segment_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort="created_at",
            order="desc",
            filters=filters or None,
            search_fields=[
                "name",
                "network",
                "application",
                "gateway",
                "address_purpose",
                "network_type",
                "location",
                "remarks",
                "start_ip",
                "end_ip",
            ],
        )
        result: list[IpSegmentResponse] = []
        for segment in items:
            counts = await self._segment_counts(segment.id)
            result.append(self._to_segment_response(segment, counts))
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return result, pagination

    async def get_segment(
        self, segment_id: uuid.UUID, *, include_addresses: bool = True
    ) -> IpSegmentDetail:
        segment = await self.segment_repo.get_by_id_active(segment_id)
        if not segment:
            raise NotFoundError("地址段不存在")
        # 打开详情前清理：已删除 / 已下架设备对应的 IP 绑定
        await self.reconcile_stale_device_binds(segment_id=segment_id)
        counts = await self._segment_counts(segment_id)
        base = self._to_segment_response(segment, counts)
        if not include_addresses:
            return IpSegmentDetail(**base.model_dump(), addresses=[])
        addresses = await self.repo.list_by_segment(segment_id)
        addresses.sort(key=lambda x: _ip_sort_key(x.system_ip))
        return IpSegmentDetail(
            **base.model_dump(),
            addresses=[self._to_response(a) for a in addresses],
        )

    async def create_segment(
        self, payload: IpSegmentCreate, user_id: uuid.UUID | None = None
    ) -> IpSegmentDetail:
        net, hosts = _expand_cidr(payload.network, payload.prefix_len)
        reserved_set = _parse_reserved_ips(
            payload.reserved_ips,
            reserved_count=payload.reserved_count,
            hosts=hosts,
        )
        gateway = payload.gateway.strip() if payload.gateway else None
        if gateway:
            try:
                ipaddress.ip_address(gateway)
            except ValueError as exc:
                raise ValidationError(f"无效网关地址: {exc}", code=10004) from exc
        for dns_val, label in ((payload.dns, "DNS"), (payload.dns_secondary, "备用 DNS")):
            if dns_val and dns_val.strip():
                try:
                    ipaddress.ip_address(dns_val.strip())
                except ValueError as exc:
                    raise ValidationError(f"无效{label}: {exc}", code=10004) from exc

        prefix_len = int(net.prefixlen)
        dotted = _prefix_to_dotted(prefix_len)
        app = payload.application.strip() if payload.application else None
        purpose = payload.address_purpose.strip() if payload.address_purpose else None
        network_type = payload.network_type.strip() if payload.network_type else None
        location = payload.location.strip() if payload.location else None
        remarks = payload.remarks.strip() if payload.remarks else None
        dns = payload.dns.strip() if payload.dns else None
        dns_secondary = payload.dns_secondary.strip() if payload.dns_secondary else None
        name = f"{app + ' · ' if app else ''}{net.network_address}/{prefix_len}"

        segment = IpSegment(
            application=app,
            network=str(net.network_address),
            prefix_len=prefix_len,
            gateway=gateway,
            address_purpose=purpose,
            network_type=network_type,
            location=location,
            remarks=remarks,
            name=name[:100],
            start_ip=hosts[0],
            end_ip=hosts[-1],
            netmask=str(prefix_len),
            dns=dns,
            dns_secondary=dns_secondary,
            application_type=purpose,
            label=app,
            description=remarks,
            created_by=user_id,
            updated_by=user_id,
        )
        created_segment = await self.segment_repo.create(segment)

        existing_map = await self.repo.map_by_system_ips(hosts, include_deleted=True)
        created = 0
        skipped = 0
        now = datetime.now(timezone.utc)

        for system_ip in hosts:
            status = (
                IpStatus.RESERVED.value
                if system_ip in reserved_set
                else IpStatus.FREE.value
            )
            existing = existing_map.get(system_ip)
            if existing is not None and existing.deleted_at is None:
                skipped += 1
                continue
            if existing is not None and existing.deleted_at is not None:
                # 复用软删记录，避免 UNIQUE(system_ip) 冲突导致 500
                existing.deleted_at = None
                existing.deleted_by = None
                existing.segment_id = created_segment.id
                existing.bmc_ip = None
                existing.vip = None
                existing.netmask = dotted
                existing.gateway = gateway
                existing.dns = dns
                existing.dns_secondary = dns_secondary
                existing.label = None
                existing.description = remarks
                existing.status = status
                existing.bind_type = IpBindType.NONE.value
                existing.device_id = None
                existing.rack_id = None
                existing.room_id = None
                existing.scope_rack_ids = None
                existing.u_position = None
                existing.updated_by = user_id
                existing.updated_at = now
                existing.version = (existing.version or 0) + 1
                created += 1
                continue

            entity = IpAddress(
                segment_id=created_segment.id,
                system_ip=system_ip,
                bmc_ip=None,
                vip=None,
                netmask=dotted,
                gateway=gateway,
                dns=dns,
                dns_secondary=dns_secondary,
                label=None,
                description=remarks,
                status=status,
                bind_type=IpBindType.NONE.value,
                created_by=user_id,
                updated_by=user_id,
            )
            self.session.add(entity)
            created += 1

        if created == 0:
            await self.segment_repo.soft_delete(created_segment, deleted_by=user_id)
            raise ValidationError(
                f"地址段创建失败：可用地址均已存在（跳过 {skipped}）", code=10004
            )
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise ValidationError(
                "地址段创建失败：部分 IP 已存在（含历史软删除冲突），请检查后重试",
                code=10004,
            ) from exc
        # 创建响应不附带全量地址，避免 /24 等大段序列化过慢；前端会再拉详情
        return await self.get_segment(created_segment.id, include_addresses=False)

    async def update_segment(
        self,
        segment_id: uuid.UUID,
        payload: IpSegmentUpdate,
        user_id: uuid.UUID | None = None,
    ) -> IpSegmentDetail:
        segment = await self.segment_repo.get_by_id_active(segment_id)
        if not segment:
            raise NotFoundError("地址段不存在")
        if payload.application is not None:
            segment.application = payload.application.strip() or None
        if payload.gateway is not None:
            gw = payload.gateway.strip() or None
            if gw:
                try:
                    ipaddress.ip_address(gw)
                except ValueError as exc:
                    raise ValidationError(f"无效网关地址: {exc}", code=10004) from exc
            segment.gateway = gw
        if payload.address_purpose is not None:
            segment.address_purpose = payload.address_purpose.strip() or None
            segment.application_type = segment.address_purpose
        elif payload.application_type is not None:
            segment.application_type = payload.application_type.strip() or None
            segment.address_purpose = segment.application_type
        if payload.network_type is not None:
            segment.network_type = payload.network_type.strip() or None
        if payload.location is not None:
            segment.location = payload.location.strip() or None
        if payload.remarks is not None:
            segment.remarks = payload.remarks
            segment.description = payload.remarks
        elif payload.description is not None:
            segment.description = payload.description
            segment.remarks = payload.description
        if payload.dns is not None:
            segment.dns = payload.dns.strip() or None
        if payload.dns_secondary is not None:
            segment.dns_secondary = payload.dns_secondary.strip() or None
        if payload.name is not None:
            segment.name = payload.name.strip()
        if payload.netmask is not None:
            segment.netmask = payload.netmask.strip() or None
        if payload.label is not None:
            segment.label = payload.label.strip() or None

        addresses = await self.repo.list_by_segment(segment_id)
        for ip in addresses:
            if payload.gateway is not None:
                ip.gateway = segment.gateway
            if payload.dns is not None:
                ip.dns = segment.dns
            if payload.dns_secondary is not None:
                ip.dns_secondary = segment.dns_secondary
            ip.updated_by = user_id
            ip.version += 1

        segment.updated_by = user_id
        segment.version += 1
        await self.session.flush()
        return await self.get_segment(segment_id)

    async def delete_segment(
        self, segment_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> None:
        segment = await self.segment_repo.get_by_id_active(segment_id)
        if not segment:
            raise NotFoundError("地址段不存在")
        addresses = await self.repo.list_by_segment(segment_id)
        for ip in addresses:
            await self.repo.soft_delete(ip, deleted_by=user_id)
        await self.segment_repo.soft_delete(segment, deleted_by=user_id)
        await self.session.flush()

    async def list_ips(
        self,
        params: PaginationParams,
        *,
        room_id: uuid.UUID | None = None,
        rack_id: uuid.UUID | None = None,
        device_id: uuid.UUID | None = None,
        segment_id: uuid.UUID | None = None,
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
        if segment_id:
            filters["segment_id"] = segment_id
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
        system_ip = payload.system_ip.strip()
        netmask = payload.netmask.strip() if payload.netmask else None
        gateway = payload.gateway.strip() if payload.gateway else None
        dns = payload.dns.strip() if payload.dns else None
        dns_secondary = payload.dns_secondary.strip() if payload.dns_secondary else None
        label = payload.label
        prefix = _guess_prefix(netmask)
        try:
            net = ipaddress.ip_network(f"{system_ip}/{prefix}", strict=False)
            network = str(net.network_address)
        except ValueError:
            network = system_ip
        segment = IpSegment(
            application=None,
            network=network,
            prefix_len=prefix,
            gateway=gateway,
            address_purpose=None,
            network_type=None,
            location=None,
            remarks=payload.description,
            name=(label or system_ip)[:100],
            start_ip=system_ip,
            end_ip=system_ip,
            netmask=str(prefix),
            dns=dns,
            dns_secondary=dns_secondary,
            application_type=None,
            label=label,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created_segment = await self.segment_repo.create(segment)
        entity = IpAddress(
            segment_id=created_segment.id,
            system_ip=system_ip,
            bmc_ip=payload.bmc_ip.strip() if payload.bmc_ip else None,
            vip=payload.vip.strip() if payload.vip else None,
            netmask=netmask,
            gateway=gateway,
            dns=dns,
            dns_secondary=dns_secondary,
            label=label,
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
        elif status == IpStatus.RESERVED.value:
            entity.status = IpStatus.RESERVED.value
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
        application_type = (
            payload.application_type.strip() if payload.application_type else None
        )
        prefix = _guess_prefix(netmask)
        try:
            net = ipaddress.ip_network(f"{system_ips[0]}/{prefix}", strict=False)
            network = str(net.network_address)
        except ValueError:
            network = system_ips[0]
        segment_name = (
            (payload.name.strip() if payload.name else None)
            or (payload.label_prefix.strip() if payload.label_prefix else None)
            or f"{network}/{prefix}"
        )
        segment = IpSegment(
            application=None,
            network=network,
            prefix_len=prefix,
            gateway=gateway,
            address_purpose=application_type,
            network_type=None,
            location=None,
            remarks=payload.description,
            name=segment_name[:100],
            start_ip=system_ips[0],
            end_ip=system_ips[-1],
            netmask=str(prefix),
            dns=dns,
            dns_secondary=dns_secondary,
            application_type=application_type,
            label=payload.label_prefix.strip() if payload.label_prefix else None,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created_segment = await self.segment_repo.create(segment)

        result = IpAddressBatchCreateResult(segment_id=str(created_segment.id))
        for idx, system_ip in enumerate(system_ips):
            if await self.repo.get_by_system_ip(system_ip):
                result.skipped += 1
                result.errors.append(f"{system_ip}: 已存在")
                continue
            label = None
            if payload.label_prefix:
                label = f"{payload.label_prefix}-{idx + 1}"
            entity = IpAddress(
                segment_id=created_segment.id,
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
        if result.created == 0:
            await self.segment_repo.soft_delete(created_segment, deleted_by=user_id)
            result.segment_id = None
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

    async def release_by_device(
        self, device_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> int:
        """解除设备上所有 IP 绑定，状态恢复为空闲（禁用/保留除外）。"""
        ips = await self.repo.list_by_device(device_id)
        if not ips:
            return 0
        released = 0
        for entity in ips:
            self._clear_device_bind(entity, user_id)
            released += 1
        await self.session.flush()
        return released

    async def release_by_devices(
        self, device_ids: list[uuid.UUID], user_id: uuid.UUID | None = None
    ) -> int:
        if not device_ids:
            return 0
        ips = await self.repo.list_by_devices(device_ids)
        if not ips:
            return 0
        released = 0
        for entity in ips:
            self._clear_device_bind(entity, user_id)
            released += 1
        await self.session.flush()
        return released

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
