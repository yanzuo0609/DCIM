import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.infrastructure import Building, DataCenter, Floor, Room
from app.repositories.base import BaseRepository

DEFAULT_FLOOR_NAME = "1F"


def location_to_code(location: str) -> str:
    base = re.sub(r"\s+", "-", location.strip())
    base = re.sub(r"[^\w\-]", "", base, flags=re.UNICODE)
    return f"DC-{(base or 'default')[:45]}"


class DataCenterRepository(BaseRepository[DataCenter]):
    model = DataCenter

    async def get_by_code(self, code: str) -> DataCenter | None:
        stmt = select(DataCenter).where(
            DataCenter.code == code,
            DataCenter.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_location(self, location: str) -> DataCenter | None:
        stmt = select(DataCenter).where(
            DataCenter.location == location,
            DataCenter.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class BuildingRepository(BaseRepository[Building]):
    model = Building

    async def get_by_name_in_datacenter(
        self, datacenter_id: uuid.UUID, name: str
    ) -> Building | None:
        stmt = select(Building).where(
            Building.datacenter_id == datacenter_id,
            Building.name == name,
            Building.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class FloorRepository(BaseRepository[Floor]):
    model = Floor

    async def get_by_name_in_building(self, building_id: uuid.UUID, name: str) -> Floor | None:
        stmt = select(Floor).where(
            Floor.building_id == building_id,
            Floor.name == name,
            Floor.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class RoomRepository(BaseRepository[Room]):
    model = Room

    async def get_by_id_with_hierarchy(self, room_id: uuid.UUID) -> Room | None:
        stmt = (
            select(Room)
            .options(
                selectinload(Room.floor)
                .selectinload(Floor.building)
                .selectinload(Building.datacenter)
            )
            .where(Room.id == room_id, Room.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_ids_with_hierarchy(self, ids: list[uuid.UUID]) -> list[Room]:
        if not ids:
            return []
        stmt = (
            select(Room)
            .options(
                selectinload(Room.floor)
                .selectinload(Floor.building)
                .selectinload(Building.datacenter)
            )
            .where(Room.id.in_(ids), Room.deleted_at.is_(None))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_ids(self, ids: list[uuid.UUID]) -> list[Room]:
        """Lightweight fetch for id/name labels (no hierarchy)."""
        if not ids:
            return []
        stmt = select(Room).where(Room.id.in_(ids), Room.deleted_at.is_(None))
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_name_in_floor(self, floor_id: uuid.UUID, name: str) -> Room | None:
        stmt = select(Room).where(
            Room.floor_id == floor_id,
            Room.name == name,
            Room.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()
