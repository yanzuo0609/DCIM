import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ip_address import IpAddress, IpSegment, IpStatus
from app.repositories.base import BaseRepository


class IpSegmentRepository(BaseRepository[IpSegment]):
    model = IpSegment

    async def list_all_active(self) -> list[IpSegment]:
        stmt = (
            select(IpSegment)
            .where(IpSegment.deleted_at.is_(None))
            .order_by(IpSegment.created_at.desc())
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_id_active(self, entity_id: uuid.UUID) -> IpSegment | None:
        stmt = select(IpSegment).where(IpSegment.id == entity_id, IpSegment.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()


class IpAddressRepository(BaseRepository[IpAddress]):
    model = IpAddress

    async def get_by_system_ip(self, system_ip: str) -> IpAddress | None:
        stmt = select(IpAddress).where(
            IpAddress.system_ip == system_ip, IpAddress.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id_full(self, entity_id: uuid.UUID) -> IpAddress | None:
        stmt = (
            select(IpAddress)
            .options(
                selectinload(IpAddress.device),
                selectinload(IpAddress.rack),
                selectinload(IpAddress.room),
            )
            .where(IpAddress.id == entity_id, IpAddress.deleted_at.is_(None))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_device(self, device_id: uuid.UUID) -> list[IpAddress]:
        stmt = (
            select(IpAddress)
            .where(IpAddress.device_id == device_id, IpAddress.deleted_at.is_(None))
            .order_by(IpAddress.system_ip)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_devices(self, device_ids: list[uuid.UUID]) -> list[IpAddress]:
        if not device_ids:
            return []
        stmt = select(IpAddress).where(
            IpAddress.device_id.in_(device_ids), IpAddress.deleted_at.is_(None)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_ids(self, ids: list[uuid.UUID]) -> list[IpAddress]:
        if not ids:
            return []
        stmt = (
            select(IpAddress)
            .options(
                selectinload(IpAddress.device),
                selectinload(IpAddress.rack),
                selectinload(IpAddress.room),
            )
            .where(IpAddress.id.in_(ids), IpAddress.deleted_at.is_(None))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_segment(self, segment_id: uuid.UUID) -> list[IpAddress]:
        stmt = (
            select(IpAddress)
            .options(
                selectinload(IpAddress.device),
                selectinload(IpAddress.rack),
                selectinload(IpAddress.room),
            )
            .where(IpAddress.segment_id == segment_id, IpAddress.deleted_at.is_(None))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_device_bound(
        self, *, segment_id: uuid.UUID | None = None
    ) -> list[IpAddress]:
        """列出仍绑定设备的 IP（含已软删设备上的残留）。"""
        filters = [
            IpAddress.deleted_at.is_(None),
            IpAddress.device_id.is_not(None),
        ]
        if segment_id is not None:
            filters.append(IpAddress.segment_id == segment_id)
        stmt = select(IpAddress).where(*filters)
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_orphans(self) -> list[IpAddress]:
        stmt = select(IpAddress).where(
            IpAddress.segment_id.is_(None), IpAddress.deleted_at.is_(None)
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_by_segment_status(self, segment_id: uuid.UUID) -> dict[str, int]:
        stmt = (
            select(IpAddress.status, func.count())
            .where(IpAddress.segment_id == segment_id, IpAddress.deleted_at.is_(None))
            .group_by(IpAddress.status)
        )
        rows = (await self.session.execute(stmt)).all()
        counts = {
            IpStatus.FREE.value: 0,
            IpStatus.ALLOCATED.value: 0,
            IpStatus.DISABLED.value: 0,
            IpStatus.RESERVED.value: 0,
        }
        total = 0
        for status, count in rows:
            key = status or IpStatus.FREE.value
            counts[key] = int(count)
            total += int(count)
        counts["total"] = total
        return counts
