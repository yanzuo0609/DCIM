from decimal import Decimal

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.device import Device
from app.models.infrastructure import DataCenter, Room
from app.models.rack import Rack, RackPosition
from app.schemas.dashboard import DashboardSummary, DashboardUtilization, UtilizationItem


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

    async def _count(self, model) -> int:
        stmt = select(func.count()).select_from(model).where(model.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one()
