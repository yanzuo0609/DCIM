import math
import uuid
from datetime import datetime, timezone
from typing import Generic, TypeVar

from sqlalchemy import Select, asc, desc, false, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.base import BaseModel

T = TypeVar("T", bound=BaseModel)


class BaseRepository(Generic[T]):
    model: type[T]

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    def _active_filter(self, stmt: Select[tuple[T]]) -> Select[tuple[T]]:
        return stmt.where(self.model.deleted_at.is_(None))

    async def get_by_id(self, entity_id: uuid.UUID) -> T | None:
        stmt = select(self.model).where(self.model.id == entity_id)
        stmt = self._active_filter(stmt)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_paginated(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
        filters: dict | None = None,
        in_filters: dict | None = None,
        search_fields: list | None = None,
    ) -> tuple[list[T], int]:
        stmt = select(self.model)
        stmt = self._active_filter(stmt)

        if filters:
            for key, value in filters.items():
                if value is not None and hasattr(self.model, key):
                    stmt = stmt.where(getattr(self.model, key) == value)

        if in_filters:
            for key, values in in_filters.items():
                if values is None or not hasattr(self.model, key):
                    continue
                # 空列表必须得到空结果，避免误返回全表
                if len(values) == 0:
                    stmt = stmt.where(false())
                else:
                    stmt = stmt.where(getattr(self.model, key).in_(values))

        if keyword and search_fields:
            clauses = [
                getattr(self.model, field).ilike(f"%{keyword}%")
                for field in search_fields
                if hasattr(self.model, field)
            ]
            if clauses:
                stmt = stmt.where(or_(*clauses))

        count_stmt = select(func.count()).select_from(stmt.subquery())
        total = (await self.session.execute(count_stmt)).scalar_one()

        sort_column = getattr(self.model, sort, self.model.created_at)
        order_fn = desc if order.lower() == "desc" else asc
        stmt = stmt.order_by(order_fn(sort_column))
        stmt = stmt.offset((page - 1) * page_size).limit(page_size)

        result = await self.session.execute(stmt)
        return list(result.scalars().all()), total

    async def create(self, entity: T) -> T:
        self.session.add(entity)
        await self.session.flush()
        await self.session.refresh(entity)
        return entity

    async def soft_delete(self, entity: T, deleted_by: uuid.UUID | None = None) -> None:
        entity.deleted_at = datetime.now(timezone.utc)
        entity.deleted_by = deleted_by
        await self.session.flush()
