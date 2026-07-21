import uuid

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.infrastructure import Room
from app.models.rack import Rack, RackPosition, RackTemplate
from app.repositories.base import BaseRepository


class RackTemplateRepository(BaseRepository[RackTemplate]):
    model = RackTemplate

    async def get_by_code(self, code: str) -> RackTemplate | None:
        stmt = select(RackTemplate).where(
            RackTemplate.code == code,
            RackTemplate.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class RackRepository(BaseRepository[Rack]):
    model = Rack

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
        filters: dict | None = None,
        search_fields: list | None = None,
        only_active_rooms: bool = True,
    ) -> tuple[list[Rack], int]:
        """List active racks; by default hide racks whose room was soft-deleted."""
        from sqlalchemy import asc, desc, func, or_

        stmt = select(Rack).where(Rack.deleted_at.is_(None))
        if only_active_rooms:
            stmt = stmt.join(Room, Room.id == Rack.room_id).where(Room.deleted_at.is_(None))

        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(Rack, key):
                    stmt = stmt.where(getattr(Rack, key) == value)

        if keyword and search_fields:
            clauses = [
                getattr(Rack, field).ilike(f"%{keyword}%")
                for field in search_fields
                if hasattr(Rack, field)
            ]
            if clauses:
                stmt = stmt.where(or_(*clauses))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        sort_column = getattr(Rack, sort, Rack.created_at)
        order_fn = desc if order.lower() == "desc" else asc
        stmt = stmt.order_by(order_fn(sort_column))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def list_orphans_in_deleted_rooms(self) -> list[Rack]:
        stmt = (
            select(Rack)
            .join(Room, Room.id == Rack.room_id)
            .where(Rack.deleted_at.is_(None), Room.deleted_at.is_not(None))
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id_with_positions(self, rack_id: uuid.UUID) -> Rack | None:
        stmt = (
            select(Rack)
            .options(selectinload(Rack.positions))
            .where(Rack.id == rack_id, Rack.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_ids(self, ids: list[uuid.UUID]) -> list[Rack]:
        if not ids:
            return []
        stmt = select(Rack).where(Rack.id.in_(ids), Rack.deleted_at.is_(None))
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_ids_with_positions(self, ids: list[uuid.UUID]) -> list[Rack]:
        if not ids:
            return []
        stmt = (
            select(Rack)
            .options(selectinload(Rack.positions))
            .where(Rack.id.in_(ids), Rack.deleted_at.is_(None))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def get_by_code(self, code: str) -> Rack | None:
        stmt = select(Rack).where(Rack.code == code, Rack.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_code_in_room(
        self, room_id: uuid.UUID, code: str, *, active_only: bool = True
    ) -> Rack | None:
        stmt = select(Rack).where(Rack.room_id == room_id, Rack.code == code)
        if active_only:
            stmt = stmt.where(Rack.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def code_exists(
        self, code: str, exclude_id: uuid.UUID | None = None
    ) -> bool:
        """Legacy helper: any room. Prefer code_exists_in_room for new logic."""
        stmt = select(Rack.id).where(Rack.code == code, Rack.deleted_at.is_(None))
        if exclude_id is not None:
            stmt = stmt.where(Rack.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def code_exists_in_room(
        self,
        room_id: uuid.UUID,
        code: str,
        exclude_id: uuid.UUID | None = None,
        *,
        include_deleted: bool = True,
    ) -> bool:
        stmt = select(Rack.id).where(Rack.room_id == room_id, Rack.code == code)
        if not include_deleted:
            stmt = stmt.where(Rack.deleted_at.is_(None))
        if exclude_id is not None:
            stmt = stmt.where(Rack.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_soft_deleted_holding_identity(
        self, room_id: uuid.UUID, identity: str
    ) -> list[Rack]:
        stmt = select(Rack).where(
            Rack.room_id == room_id,
            Rack.deleted_at.is_not(None),
            or_(Rack.code == identity, Rack.name == identity),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_name_in_room(self, room_id: uuid.UUID, name: str) -> Rack | None:
        stmt = select(Rack).where(
            Rack.room_id == room_id,
            Rack.name == name,
            Rack.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def name_exists_in_room(
        self,
        room_id: uuid.UUID,
        name: str,
        exclude_id: uuid.UUID | None = None,
    ) -> bool:
        # Include soft-deleted: uk_rack_room_name applies to all rows.
        stmt = select(Rack.id).where(Rack.room_id == room_id, Rack.name == name)
        if exclude_id is not None:
            stmt = stmt.where(Rack.id != exclude_id)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def list_by_room(self, room_id: uuid.UUID) -> list[Rack]:
        stmt = select(Rack).where(Rack.room_id == room_id, Rack.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_room_and_template(
        self, room_id: uuid.UUID, template_id: uuid.UUID
    ) -> list[Rack]:
        stmt = select(Rack).where(
            Rack.room_id == room_id,
            Rack.rack_template_id == template_id,
            Rack.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def template_usage_rows(
        self, template_ids: list[uuid.UUID] | None = None
    ) -> list[tuple[uuid.UUID, uuid.UUID, int]]:
        """Return (template_id, room_id, rack_count) for active racks bound to templates."""
        stmt = (
            select(Rack.rack_template_id, Rack.room_id, func.count(Rack.id))
            .where(
                Rack.deleted_at.is_(None),
                Rack.rack_template_id.is_not(None),
            )
            .group_by(Rack.rack_template_id, Rack.room_id)
        )
        if template_ids is not None:
            if not template_ids:
                return []
            stmt = stmt.where(Rack.rack_template_id.in_(template_ids))
        result = await self.session.execute(stmt)
        rows: list[tuple[uuid.UUID, uuid.UUID, int]] = []
        for template_id, room_id, count in result.all():
            if template_id is None:
                continue
            rows.append((template_id, room_id, int(count)))
        return rows

    async def get_by_position_in_room(
        self, room_id: uuid.UUID, row_no: int, column_no: int
    ) -> Rack | None:
        stmt = select(Rack).where(
            Rack.room_id == room_id,
            Rack.row_no == row_no,
            Rack.column_no == column_no,
            Rack.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()


class RackPositionRepository(BaseRepository[RackPosition]):
    model = RackPosition

    async def count_occupied(self, rack_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(RackPosition).where(
            RackPosition.rack_id == rack_id,
            RackPosition.occupied.is_(True),
            RackPosition.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one()

    async def stats_for_rack_ids(
        self, ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, tuple[int, int]]:
        """Return {rack_id: (occupied_u, device_count)} without loading position rows."""
        from sqlalchemy import case, distinct

        if not ids:
            return {}
        occupied_expr = func.coalesce(
            func.sum(case((RackPosition.occupied.is_(True), 1), else_=0)),
            0,
        )
        device_expr = func.count(
            distinct(
                case(
                    (
                        (RackPosition.occupied.is_(True))
                        & (RackPosition.device_id.is_not(None)),
                        RackPosition.device_id,
                    ),
                    else_=None,
                )
            )
        )
        stmt = (
            select(RackPosition.rack_id, occupied_expr, device_expr)
            .where(
                RackPosition.rack_id.in_(ids),
                RackPosition.deleted_at.is_(None),
            )
            .group_by(RackPosition.rack_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {rack_id: (int(occupied or 0), int(devices or 0)) for rack_id, occupied, devices in rows}

    async def list_by_rack(self, rack_id: uuid.UUID) -> list[RackPosition]:
        stmt = (
            select(RackPosition)
            .where(
                RackPosition.rack_id == rack_id,
                RackPosition.deleted_at.is_(None),
            )
            .order_by(RackPosition.u_position)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
