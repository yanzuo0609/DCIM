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

    async def list_codes(self) -> list[str]:
        stmt = select(DataCenter.code).where(DataCenter.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return [str(c) for c in result.scalars().all() if c]

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

    async def list_by_datacenter(self, datacenter_id: uuid.UUID) -> list[Building]:
        stmt = select(Building).where(
            Building.datacenter_id == datacenter_id,
            Building.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


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

    async def list_by_building_ids(self, building_ids: list[uuid.UUID]) -> list[Floor]:
        if not building_ids:
            return []
        stmt = select(Floor).where(
            Floor.building_id.in_(building_ids),
            Floor.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class RoomRepository(BaseRepository[Room]):
    model = Room

    async def count_by_datacenter(self, datacenter_id: uuid.UUID) -> int:
        from sqlalchemy import func

        stmt = (
            select(func.count())
            .select_from(Room)
            .join(Floor, Floor.id == Room.floor_id)
            .join(Building, Building.id == Floor.building_id)
            .where(
                Room.deleted_at.is_(None),
                Floor.deleted_at.is_(None),
                Building.deleted_at.is_(None),
                Building.datacenter_id == datacenter_id,
            )
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def list_by_datacenter(self, datacenter_id: uuid.UUID) -> list[Room]:
        stmt = (
            select(Room)
            .join(Floor, Floor.id == Room.floor_id)
            .join(Building, Building.id == Floor.building_id)
            .where(
                Room.deleted_at.is_(None),
                Floor.deleted_at.is_(None),
                Building.deleted_at.is_(None),
                Building.datacenter_id == datacenter_id,
            )
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

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

    async def list_paginated_by_datacenter(
        self,
        *,
        datacenter_id: uuid.UUID,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
    ) -> tuple[list[Room], int]:
        from sqlalchemy import asc, desc, func, or_

        stmt = (
            select(Room)
            .join(Floor, Floor.id == Room.floor_id)
            .join(Building, Building.id == Floor.building_id)
            .where(
                Room.deleted_at.is_(None),
                Floor.deleted_at.is_(None),
                Building.deleted_at.is_(None),
                Building.datacenter_id == datacenter_id,
            )
        )
        if keyword:
            stmt = stmt.where(
                or_(
                    Room.name.ilike(f"%{keyword}%"),
                    Building.name.ilike(f"%{keyword}%"),
                )
            )
        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()
        sort_column = getattr(Room, sort, Room.created_at)
        order_fn = desc if order.lower() == "desc" else asc
        stmt = stmt.order_by(order_fn(sort_column))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)
        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def get_by_name_in_floor(self, floor_id: uuid.UUID, name: str) -> Room | None:
        stmt = select(Room).where(
            Room.floor_id == floor_id,
            Room.name == name,
            Room.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code(self, code: str) -> Room | None:
        key = str(code or "").strip()
        if not key:
            return None
        stmt = select(Room).where(Room.code == key, Room.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_codes(self) -> list[str]:
        stmt = select(Room.code).where(Room.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return [str(c) for c in result.scalars().all() if c]
