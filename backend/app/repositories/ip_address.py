import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.ip_address import IpAddress
from app.repositories.base import BaseRepository


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
