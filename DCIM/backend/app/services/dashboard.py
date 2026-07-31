from datetime import datetime, timedelta

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device, DeviceContract, DeviceType
from app.models.infrastructure import Building, DataCenter, Floor, Room
from app.models.network import NetworkLink, NetworkNode, NetworkProject, NetworkTopology
from app.models.rack import Rack, RackPosition
from app.schemas.dashboard import (
    AlertRecord,
    ContractScreenStats,
    DashboardAnalytics,
    DashboardSummary,
    DashboardUtilization,
    DeviceRuntimeStats,
    DualMetric,
    NamedMetric,
    NetworkScreenStats,
    RoomMonitorLayout,
    RoomMonitorOption,
    RoomMonitorRack,
    TrendPoint,
    UtilizationItem,
)


STATUS_LABELS = {
    "stock": "库存",
    "mounted": "已上架",
    "maintenance": "维护中",
    "retired": "已退役",
    "active": "在用",
}


class DashboardService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_summary(self) -> DashboardSummary:
        dc_count = await self._count(DataCenter)
        room_count = await self._count(Room)
        rack_count = await self._count(Rack)
        device_count = await self._count(Device)

        mounted_stmt = select(func.count()).select_from(Device).where(
            Device.rack_id.is_not(None), Device.deleted_at.is_(None)
        )
        mounted_count = (await self.session.execute(mounted_stmt)).scalar_one()

        rack_stmt = select(Rack).where(Rack.deleted_at.is_(None))
        racks = list((await self.session.execute(rack_stmt)).scalars().all())
        total_u = sum(r.total_u for r in racks)

        pos_stmt = select(func.count()).select_from(RackPosition).where(
            RackPosition.occupied.is_(True), RackPosition.deleted_at.is_(None)
        )
        occupied_u = (await self.session.execute(pos_stmt)).scalar_one()
        free_u = total_u - occupied_u
        utilization = round((occupied_u / total_u) * 100, 2) if total_u else 0.0

        power_stmt = select(func.coalesce(func.sum(Device.power), 0)).where(
            Device.deleted_at.is_(None)
        )
        total_power = float((await self.session.execute(power_stmt)).scalar_one())

        return DashboardSummary(
            datacenter_count=dc_count,
            room_count=room_count,
            rack_count=rack_count,
            device_count=device_count,
            mounted_device_count=mounted_count,
            total_u=total_u,
            occupied_u=occupied_u,
            free_u=free_u,
            utilization=utilization,
            total_power=total_power,
        )

    async def get_utilization(self) -> DashboardUtilization:
        from app.repositories.rack import RackPositionRepository

        stmt = select(Rack).where(Rack.deleted_at.is_(None))
        racks = list((await self.session.execute(stmt)).scalars().all())
        stats = await RackPositionRepository(self.session).stats_for_rack_ids(
            [r.id for r in racks]
        )
        items: list[UtilizationItem] = []
        for rack in racks:
            occupied = stats.get(rack.id, (0, 0))[0]
            util = round((occupied / rack.total_u) * 100, 2) if rack.total_u else 0.0
            items.append(
                UtilizationItem(
                    rack_id=str(rack.id),
                    rack_code=rack.code,
                    rack_name=rack.name,
                    room_id=str(rack.room_id),
                    total_u=rack.total_u,
                    occupied_u=occupied,
                    utilization=util,
                )
            )
        return DashboardUtilization(items=items)

    async def get_analytics(self) -> DashboardAnalytics:
        summary = await self.get_summary()
        utilization = await self.get_utilization()
        device_by_type = await self._device_by_type()
        device_by_status = await self._device_by_status()
        runtime = self._runtime_from_status(device_by_status, summary.device_count)
        rack_util_buckets = self._rack_util_buckets(utilization.items)
        power_by_room = await self._power_by_room()
        power_by_rack = await self._power_by_rack()
        devices_by_datacenter = await self._devices_by_datacenter()
        device_trend = await self._device_trend()
        type_online_status = await self._type_online_status()
        alert_racks = sorted(
            [r for r in utilization.items if r.utilization >= 85],
            key=lambda x: x.utilization,
            reverse=True,
        )[:15]
        alert_records = [
            AlertRecord(
                code=r.rack_code,
                device_name=r.rack_name or r.rack_code,
                event_time=f"{r.utilization}%",
                value=f"{r.occupied_u}/{r.total_u}U",
            )
            for r in alert_racks[:8]
        ]
        mount_ratio = (
            round((summary.mounted_device_count / summary.device_count) * 100, 2)
            if summary.device_count
            else 0.0
        )
        return DashboardAnalytics(
            summary=summary,
            utilization=utilization,
            device_by_type=device_by_type,
            device_by_status=device_by_status,
            rack_util_buckets=rack_util_buckets,
            power_by_room=power_by_room,
            power_by_rack=power_by_rack,
            devices_by_datacenter=devices_by_datacenter,
            device_trend=device_trend,
            type_online_status=type_online_status,
            runtime=runtime,
            alert_racks=alert_racks,
            alert_records=alert_records,
            mount_ratio=mount_ratio,
            network=await self._network_stats(),
            contract=await self._contract_stats(),
            generated_at=datetime.now(),
        )

    def _runtime_from_status(
        self, status_rows: list[NamedMetric], total: int
    ) -> DeviceRuntimeStats:
        by_code = {(r.code or "").lower(): int(r.value) for r in status_rows}
        running = by_code.get("mounted", 0) + by_code.get("active", 0)
        fault = by_code.get("maintenance", 0)
        offline = by_code.get("retired", 0)
        repair = by_code.get("stock", 0)
        total = total or (running + fault + offline + repair)
        ratio = round((running / total) * 100, 1) if total else 0.0
        return DeviceRuntimeStats(
            total=total,
            running=running,
            fault=fault,
            offline=offline,
            repair=repair,
            running_ratio=ratio,
        )

    async def _device_by_type(self) -> list[NamedMetric]:
        stmt = (
            select(
                func.coalesce(DeviceType.name, "未分类").label("name"),
                func.coalesce(DeviceType.code, "unknown").label("code"),
                func.count(Device.id).label("cnt"),
            )
            .select_from(Device)
            .outerjoin(DeviceType, Device.device_type_id == DeviceType.id)
            .where(Device.deleted_at.is_(None))
            .group_by(DeviceType.name, DeviceType.code)
            .order_by(func.count(Device.id).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [NamedMetric(name=r.name, code=r.code, value=float(r.cnt)) for r in rows]

    async def _device_by_status(self) -> list[NamedMetric]:
        stmt = (
            select(Device.status, func.count(Device.id))
            .where(Device.deleted_at.is_(None))
            .group_by(Device.status)
            .order_by(func.count(Device.id).desc())
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            NamedMetric(
                name=STATUS_LABELS.get(str(status), str(status or "未知")),
                code=str(status) if status else None,
                value=float(cnt),
            )
            for status, cnt in rows
        ]

    def _rack_util_buckets(self, items: list[UtilizationItem]) -> list[NamedMetric]:
        buckets = [
            ("0-30%", 0, 30),
            ("30-60%", 30, 60),
            ("60-85%", 60, 85),
            ("85-100%", 85, 101),
        ]
        return [
            NamedMetric(
                name=name,
                code=name,
                value=float(sum(1 for i in items if lo <= i.utilization < hi)),
            )
            for name, lo, hi in buckets
        ]

    async def _power_by_room(self) -> list[NamedMetric]:
        stmt = (
            select(Room.name, func.coalesce(func.sum(Device.power), 0))
            .select_from(Device)
            .join(Rack, Device.rack_id == Rack.id)
            .join(Room, Rack.room_id == Room.id)
            .where(Device.deleted_at.is_(None), Rack.deleted_at.is_(None), Room.deleted_at.is_(None))
            .group_by(Room.id, Room.name)
            .order_by(func.coalesce(func.sum(Device.power), 0).desc())
            .limit(12)
        )
        rows = (await self.session.execute(stmt)).all()
        return [NamedMetric(name=name or "未知机房", value=float(power or 0)) for name, power in rows]

    async def _power_by_rack(self) -> list[NamedMetric]:
        stmt = (
            select(Rack.code, func.coalesce(func.sum(Device.power), 0))
            .select_from(Device)
            .join(Rack, Device.rack_id == Rack.id)
            .where(Device.deleted_at.is_(None), Rack.deleted_at.is_(None))
            .group_by(Rack.id, Rack.code)
            .order_by(func.coalesce(func.sum(Device.power), 0).desc())
            .limit(8)
        )
        rows = (await self.session.execute(stmt)).all()
        return [NamedMetric(name=code or "未知", value=float(power or 0)) for code, power in rows]

    async def _devices_by_datacenter(self) -> list[NamedMetric]:
        stmt = (
            select(DataCenter.name, func.count(Device.id))
            .select_from(Device)
            .join(Rack, Device.rack_id == Rack.id)
            .join(Room, Rack.room_id == Room.id)
            .join(Floor, Room.floor_id == Floor.id)
            .join(Building, Floor.building_id == Building.id)
            .join(DataCenter, Building.datacenter_id == DataCenter.id)
            .where(
                Device.deleted_at.is_(None),
                Rack.deleted_at.is_(None),
                Room.deleted_at.is_(None),
                Floor.deleted_at.is_(None),
                Building.deleted_at.is_(None),
                DataCenter.deleted_at.is_(None),
            )
            .group_by(DataCenter.id, DataCenter.name)
            .order_by(func.count(Device.id).desc())
            .limit(8)
        )
        rows = (await self.session.execute(stmt)).all()
        if rows:
            return [NamedMetric(name=name or "未知", value=float(cnt)) for name, cnt in rows]
        # 未上架设备无法挂到数据中心时，回退为数据中心清单（数量 0）
        dc_stmt = select(DataCenter.name).where(DataCenter.deleted_at.is_(None)).limit(8)
        names = (await self.session.execute(dc_stmt)).scalars().all()
        return [NamedMetric(name=n, value=0) for n in names]

    async def _device_trend(self) -> list[TrendPoint]:
        # 近 6 个月新增设备累计趋势
        now = datetime.now()
        points: list[TrendPoint] = []
        cumulative = 0
        for i in range(5, -1, -1):
            month_start = datetime(now.year, now.month, 1) - timedelta(days=30 * i)
            # 简化：按自然月边界
            y = month_start.year
            m = month_start.month
            label = f"{y}-{m:02d}"
            if m == 12:
                next_y, next_m = y + 1, 1
            else:
                next_y, next_m = y, m + 1
            start = datetime(y, m, 1)
            end = datetime(next_y, next_m, 1)
            stmt = select(func.count()).select_from(Device).where(
                Device.deleted_at.is_(None),
                Device.created_at >= start,
                Device.created_at < end,
            )
            cnt = (await self.session.execute(stmt)).scalar_one()
            cumulative += int(cnt)
            points.append(TrendPoint(label=label, value=float(cumulative)))
        # 若累计全 0，用总数做平缓演示点
        if points and all(p.value == 0 for p in points) is False:
            return points
        total = await self._count(Device)
        if total:
            step = max(1, total // 6)
            return [
                TrendPoint(label=p.label, value=float(min(total, step * (i + 1))))
                for i, p in enumerate(points)
            ]
        return points

    async def _type_online_status(self) -> list[DualMetric]:
        normal_case = case(
            (Device.status.in_(["mounted", "active"]), 1),
            (Device.rack_id.is_not(None), 1),
            else_=0,
        )
        abnormal_case = case(
            (Device.status.in_(["maintenance", "retired"]), 1),
            else_=0,
        )
        stmt = (
            select(
                func.coalesce(DeviceType.name, "未分类").label("name"),
                func.coalesce(DeviceType.code, "unknown").label("code"),
                func.coalesce(func.sum(normal_case), 0).label("normal"),
                func.coalesce(func.sum(abnormal_case), 0).label("abnormal"),
            )
            .select_from(Device)
            .outerjoin(DeviceType, Device.device_type_id == DeviceType.id)
            .where(Device.deleted_at.is_(None))
            .group_by(DeviceType.name, DeviceType.code)
            .order_by(func.count(Device.id).desc())
            .limit(8)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            DualMetric(
                name=r.name,
                code=r.code,
                normal=float(r.normal or 0),
                abnormal=float(r.abnormal or 0),
            )
            for r in rows
        ]

    async def _network_stats(self) -> NetworkScreenStats:
        return NetworkScreenStats(
            project_count=await self._count(NetworkProject),
            topology_count=await self._count(NetworkTopology),
            node_count=await self._count(NetworkNode),
            link_count=await self._count(NetworkLink),
        )

    async def _contract_stats(self) -> ContractScreenStats:
        contract_count = await self._count(DeviceContract)
        qty_stmt = select(func.coalesce(func.sum(DeviceContract.quantity), 0)).where(
            DeviceContract.deleted_at.is_(None)
        )
        purchase_quantity = int((await self.session.execute(qty_stmt)).scalar_one() or 0)
        linked_stmt = select(func.count()).select_from(Device).where(
            Device.contract_id.is_not(None), Device.deleted_at.is_(None)
        )
        linked_count = (await self.session.execute(linked_stmt)).scalar_one()
        summary_rows = contract_count
        try:
            stmt = select(DeviceContract).where(DeviceContract.deleted_at.is_(None))
            contracts = list((await self.session.execute(stmt)).scalars().all())
            names: set[str] = set()
            for c in contracts:
                if c.device_items and isinstance(c.device_items, list):
                    for item in c.device_items:
                        if isinstance(item, dict) and item.get("device_name"):
                            names.add(str(item["device_name"]).strip())
                elif c.device_name:
                    for part in str(c.device_name).split(","):
                        if part.strip():
                            names.add(part.strip())
            summary_rows = len(names) or contract_count
        except Exception:  # noqa: BLE001
            summary_rows = contract_count
        return ContractScreenStats(
            contract_count=contract_count,
            purchase_quantity=purchase_quantity,
            linked_count=linked_count,
            summary_rows=summary_rows,
        )

    async def list_room_monitor_options(self) -> list[RoomMonitorOption]:
        rack_count_sq = (
            select(Rack.room_id, func.count().label("rack_count"))
            .where(Rack.deleted_at.is_(None))
            .group_by(Rack.room_id)
            .subquery()
        )
        stmt = (
            select(Room, DataCenter.name, DataCenter.location, rack_count_sq.c.rack_count)
            .outerjoin(Floor, Floor.id == Room.floor_id)
            .outerjoin(Building, Building.id == Floor.building_id)
            .outerjoin(DataCenter, DataCenter.id == Building.datacenter_id)
            .outerjoin(rack_count_sq, rack_count_sq.c.room_id == Room.id)
            .where(Room.deleted_at.is_(None))
            .order_by(func.coalesce(DataCenter.name, ""), Room.name)
        )
        rows = (await self.session.execute(stmt)).all()
        return [
            RoomMonitorOption(
                id=str(room.id),
                name=room.name,
                datacenter_name=dc_name,
                location=dc_location or dc_name,
                rack_count=int(rack_count or 0),
            )
            for room, dc_name, dc_location, rack_count in rows
        ]

    async def get_room_monitor_layout(self, room_id) -> RoomMonitorLayout:
        import uuid as uuid_mod

        from app.repositories.rack import RackPositionRepository

        rid = room_id if isinstance(room_id, uuid_mod.UUID) else uuid_mod.UUID(str(room_id))
        stmt = (
            select(Room, DataCenter.name, DataCenter.location)
            .outerjoin(Floor, Floor.id == Room.floor_id)
            .outerjoin(Building, Building.id == Floor.building_id)
            .outerjoin(DataCenter, DataCenter.id == Building.datacenter_id)
            .where(Room.id == rid, Room.deleted_at.is_(None))
        )
        row = (await self.session.execute(stmt)).one_or_none()
        if row is None:
            from app.core.exceptions import NotFoundError

            raise NotFoundError("机房不存在")
        room, dc_name, dc_location = row
        row_layout = room.get_row_layout()
        slot_codes = room.get_slot_codes()

        rack_stmt = (
            select(Rack)
            .where(Rack.room_id == rid, Rack.deleted_at.is_(None))
            .order_by(Rack.row_no, Rack.column_no, Rack.code)
        )
        racks = list((await self.session.execute(rack_stmt)).scalars().all())
        stats = await RackPositionRepository(self.session).stats_for_rack_ids([r.id for r in racks])

        monitor_racks: list[RoomMonitorRack] = []
        for rack in racks:
            occupied, device_count = stats.get(rack.id, (0, 0))
            util = round((occupied / rack.total_u) * 100, 2) if rack.total_u else 0.0
            monitor_racks.append(
                RoomMonitorRack(
                    id=str(rack.id),
                    code=rack.code,
                    name=rack.name,
                    row_no=rack.row_no,
                    column_no=rack.column_no,
                    total_u=rack.total_u,
                    occupied_u=occupied,
                    utilization=util,
                    device_count=device_count,
                    status=rack.status,
                )
            )

        return RoomMonitorLayout(
            room_id=str(room.id),
            room_name=room.name,
            datacenter_name=dc_name,
            location=dc_location or dc_name,
            rack_rows=len(row_layout),
            rack_columns=max(row_layout) if row_layout else 0,
            row_layout=row_layout,
            slot_codes=slot_codes,
            code_prefix=room.code_prefix or "A",
            code_mode=room.code_mode or "auto",
            pillar_layout=room.pillar_layout if isinstance(room.pillar_layout, dict) else None,
            racks=monitor_racks,
        )

    async def _count(self, model) -> int:
        stmt = select(func.count()).select_from(model).where(model.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one()
