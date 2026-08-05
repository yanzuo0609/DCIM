"""Personnel repositories."""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.personnel import (
    PersonnelInternal,
    PersonnelOrgChart,
    PersonnelOrgLink,
    PersonnelOrgNode,
    PersonnelSupplier,
    PersonnelSupplierContract,
    PersonnelSupplierProduct,
)
from app.repositories.base import BaseRepository


class PersonnelOrgChartRepository(BaseRepository[PersonnelOrgChart]):
    model = PersonnelOrgChart

    async def get_with_graph(self, chart_id: uuid.UUID) -> PersonnelOrgChart | None:
        stmt = (
            select(PersonnelOrgChart)
            .options(
                selectinload(PersonnelOrgChart.nodes),
                selectinload(PersonnelOrgChart.links),
            )
            .where(PersonnelOrgChart.id == chart_id, PersonnelOrgChart.deleted_at.is_(None))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_project(self, project_no: str | None = None) -> list[PersonnelOrgChart]:
        stmt = select(PersonnelOrgChart).where(PersonnelOrgChart.deleted_at.is_(None))
        if project_no:
            stmt = stmt.where(PersonnelOrgChart.project_no == project_no)
        stmt = stmt.order_by(PersonnelOrgChart.updated_at.desc())
        return list((await self.session.execute(stmt)).scalars().all())


class PersonnelOrgNodeRepository(BaseRepository[PersonnelOrgNode]):
    model = PersonnelOrgNode


class PersonnelOrgLinkRepository(BaseRepository[PersonnelOrgLink]):
    model = PersonnelOrgLink


class PersonnelInternalRepository(BaseRepository[PersonnelInternal]):
    model = PersonnelInternal


class PersonnelSupplierRepository(BaseRepository[PersonnelSupplier]):
    model = PersonnelSupplier

    async def get_with_relations(self, supplier_id: uuid.UUID) -> PersonnelSupplier | None:
        stmt = (
            select(PersonnelSupplier)
            .options(
                selectinload(PersonnelSupplier.contracts),
                selectinload(PersonnelSupplier.products),
            )
            .where(
                PersonnelSupplier.id == supplier_id,
                PersonnelSupplier.deleted_at.is_(None),
            )
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_with_relations(
        self,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        manufacturer_id: uuid.UUID | None = None,
    ) -> tuple[list[PersonnelSupplier], int]:
        filters = {}
        if manufacturer_id:
            filters["manufacturer_id"] = manufacturer_id
        items, total = await self.list_paginated(
            page=page,
            page_size=page_size,
            keyword=keyword,
            filters=filters or None,
            search_fields=["name", "role_title", "phone", "email", "wechat"],
        )
        # reload with relations
        if not items:
            return [], total
        ids = [i.id for i in items]
        stmt = (
            select(PersonnelSupplier)
            .options(
                selectinload(PersonnelSupplier.contracts),
                selectinload(PersonnelSupplier.products),
            )
            .where(PersonnelSupplier.id.in_(ids), PersonnelSupplier.deleted_at.is_(None))
        )
        loaded = list((await self.session.execute(stmt)).scalars().all())
        by_id = {x.id: x for x in loaded}
        ordered = [by_id[i] for i in ids if i in by_id]
        return ordered, total


class PersonnelSupplierContractRepository(BaseRepository[PersonnelSupplierContract]):
    model = PersonnelSupplierContract


class PersonnelSupplierProductRepository(BaseRepository[PersonnelSupplierProduct]):
    model = PersonnelSupplierProduct
