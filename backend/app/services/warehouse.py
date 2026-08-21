"""Warehouse (库房) service — ledger linked to a specific room + asset inventory."""

from __future__ import annotations

import math
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.infrastructure import Warehouse, WarehouseAsset
from app.repositories.infrastructure import (
    RoomRepository,
    WarehouseAssetRepository,
    WarehouseRepository,
)
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.infrastructure import (
    WarehouseAssetCreate,
    WarehouseAssetResponse,
    WarehouseAssetUpdate,
    WarehouseCreate,
    WarehouseResponse,
    WarehouseUpdate,
)


def _next_wh_code(codes: list[str]) -> str:
    max_n = 0
    for raw in codes:
        m = re.fullmatch(r"WH(\d+)", str(raw or "").strip().upper())
        if m:
            max_n = max(max_n, int(m.group(1)))
    return f"WH{max_n + 1}"


def _to_warehouse_response(entity: Warehouse, *, asset_count: int = 0) -> WarehouseResponse:
    room_name = None
    room_no = None
    building_no = None
    datacenter_id = None
    datacenter_name = None
    room = getattr(entity, "room", None)
    if room is not None:
        room_name = room.name
        room_no = room.name
        floor = getattr(room, "floor", None)
        if floor and floor.building:
            building_no = floor.building.name
            dc = floor.building.datacenter
            if dc:
                datacenter_id = str(dc.id)
                datacenter_name = dc.name
    return WarehouseResponse(
        id=str(entity.id),
        code=entity.code,
        name=entity.name,
        room_id=str(entity.room_id),
        room_name=room_name,
        room_no=room_no,
        building_no=building_no,
        datacenter_id=datacenter_id,
        datacenter_name=datacenter_name,
        description=entity.description,
        asset_ledger_ready=bool(getattr(entity, "asset_ledger_ready", True)),
        asset_count=max(0, int(asset_count)),
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _to_asset_response(entity: WarehouseAsset) -> WarehouseAssetResponse:
    return WarehouseAssetResponse(
        id=str(entity.id),
        warehouse_id=str(entity.warehouse_id),
        name=entity.name,
        quantity=max(1, int(getattr(entity, "quantity", 1) or 1)),
        unit=getattr(entity, "unit", None) or "piece",
        project=entity.project,
        application=entity.application,
        category=entity.category,
        status=entity.status,
        inbound_at=entity.inbound_at,
        outbound_mode=entity.outbound_mode or "undetermined",
        outbound_at=entity.outbound_at,
        owner_name=entity.owner_name,
        owner_contact=entity.owner_contact,
        remark=entity.remark,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class WarehouseService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = WarehouseRepository(session)
        self.asset_repo = WarehouseAssetRepository(session)
        self.room_repo = RoomRepository(session)
        self.session = session

    async def _allocate_code(self, preferred: str | None = None) -> str:
        preferred_clean = str(preferred or "").strip().upper()
        if preferred_clean:
            existing = await self.repo.get_by_code(preferred_clean)
            if existing is not None:
                raise ConflictError("库房编号已存在", code=10002)
            return preferred_clean
        codes = await self.repo.list_codes()
        for _ in range(1000):
            code = _next_wh_code(codes)
            hit = await self.repo.get_by_code(code)
            if hit is None:
                return code
            codes.append(code)
        return f"WH{uuid.uuid4().hex[:6].upper()}"

    async def _require_warehouse(self, warehouse_id: uuid.UUID) -> Warehouse:
        entity = await self.repo.get_by_id(warehouse_id)
        if not entity:
            raise NotFoundError("库房不存在", code=10001)
        return entity

    async def list(
        self,
        params: PaginationParams,
        *,
        room_id: uuid.UUID | None = None,
        datacenter_id: uuid.UUID | None = None,
    ) -> tuple[list[WarehouseResponse], PaginationMeta]:
        items, total = await self.repo.list_paginated_filtered(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            room_id=room_id,
            datacenter_id=datacenter_id,
            sort=params.sort,
            order=params.order,
        )
        enriched = await self.repo.list_by_ids_with_hierarchy([i.id for i in items])
        by_id = {w.id: w for w in enriched}
        ordered = [by_id[i.id] for i in items if i.id in by_id]
        counts = await self.repo.asset_counts_for_ids([w.id for w in ordered])
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [
            _to_warehouse_response(w, asset_count=counts.get(w.id, 0)) for w in ordered
        ], pagination

    async def get(self, entity_id: uuid.UUID) -> WarehouseResponse:
        entity = await self.repo.get_by_id_with_hierarchy(entity_id)
        if not entity:
            raise NotFoundError("库房不存在", code=10001)
        counts = await self.repo.asset_counts_for_ids([entity.id])
        return _to_warehouse_response(entity, asset_count=counts.get(entity.id, 0))

    async def create(
        self, payload: WarehouseCreate, user_id: uuid.UUID | None = None
    ) -> WarehouseResponse:
        try:
            room_id = uuid.UUID(str(payload.room_id))
        except ValueError as exc:
            raise ValidationError("机房 ID 格式无效", code=10004) from exc
        room = await self.room_repo.get_by_id(room_id)
        if not room:
            raise NotFoundError("机房不存在", code=10001)
        code = await self._allocate_code(payload.code)
        entity = Warehouse(
            room_id=room_id,
            code=code,
            name=payload.name.strip(),
            description=payload.description,
            asset_ledger_ready=True,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        # 创建库房后自动挂接空的资产出入库清单（asset_ledger_ready=True，条目可随时追加）
        await self.session.flush()
        loaded = await self.repo.get_by_id_with_hierarchy(created.id)
        assert loaded is not None
        return _to_warehouse_response(loaded, asset_count=0)

    async def update(
        self,
        entity_id: uuid.UUID,
        payload: WarehouseUpdate,
        user_id: uuid.UUID | None = None,
    ) -> WarehouseResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("库房不存在", code=10001)

        if payload.room_id is not None:
            try:
                room_id = uuid.UUID(str(payload.room_id))
            except ValueError as exc:
                raise ValidationError("机房 ID 格式无效", code=10004) from exc
            room = await self.room_repo.get_by_id(room_id)
            if not room:
                raise NotFoundError("机房不存在", code=10001)
            entity.room_id = room_id

        if payload.code is not None:
            next_code = str(payload.code).strip().upper()
            if not next_code:
                raise ValidationError("库房编号不能为空", code=10004)
            conflict = await self.repo.get_by_code(next_code)
            if conflict is not None and conflict.id != entity.id:
                raise ConflictError("库房编号已存在", code=10002)
            entity.code = next_code

        if payload.name is not None:
            entity.name = payload.name.strip()
        if payload.description is not None:
            entity.description = payload.description

        if not getattr(entity, "asset_ledger_ready", True):
            entity.asset_ledger_ready = True

        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        loaded = await self.repo.get_by_id_with_hierarchy(entity.id)
        assert loaded is not None
        counts = await self.repo.asset_counts_for_ids([entity.id])
        return _to_warehouse_response(loaded, asset_count=counts.get(entity.id, 0))

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("库房不存在", code=10001)
        # soft-delete assets under warehouse
        assets, _ = await self.asset_repo.list_by_warehouse_paginated(
            entity_id, page=1, page_size=5000
        )
        for asset in assets:
            await self.asset_repo.soft_delete(asset, deleted_by=user_id)
        await self.repo.soft_delete(entity, deleted_by=user_id)

    async def list_assets(
        self,
        warehouse_id: uuid.UUID,
        params: PaginationParams,
    ) -> tuple[list[WarehouseAssetResponse], PaginationMeta]:
        await self._require_warehouse(warehouse_id)
        items, total = await self.asset_repo.list_by_warehouse_paginated(
            warehouse_id,
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort,
            order=params.order,
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [_to_asset_response(i) for i in items], pagination

    async def create_asset(
        self,
        warehouse_id: uuid.UUID,
        payload: WarehouseAssetCreate,
        user_id: uuid.UUID | None = None,
    ) -> WarehouseAssetResponse:
        warehouse = await self._require_warehouse(warehouse_id)
        if not getattr(warehouse, "asset_ledger_ready", True):
            warehouse.asset_ledger_ready = True
        outbound_mode = payload.outbound_mode or "undetermined"
        entity = WarehouseAsset(
            warehouse_id=warehouse_id,
            name=payload.name.strip(),
            quantity=max(1, int(payload.quantity or 1)),
            unit=payload.unit or "piece",
            project=(payload.project or "").strip() or None,
            application=(payload.application or "").strip() or None,
            category=payload.category,
            status=payload.status,
            inbound_at=payload.inbound_at or datetime.now(timezone.utc),
            outbound_mode=outbound_mode,
            outbound_at=None if outbound_mode == "undetermined" else payload.outbound_at,
            owner_name=(payload.owner_name or "").strip() or None,
            owner_contact=(payload.owner_contact or "").strip() or None,
            remark=payload.remark,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.asset_repo.create(entity)
        return _to_asset_response(created)

    async def update_asset(
        self,
        warehouse_id: uuid.UUID,
        asset_id: uuid.UUID,
        payload: WarehouseAssetUpdate,
        user_id: uuid.UUID | None = None,
    ) -> WarehouseAssetResponse:
        await self._require_warehouse(warehouse_id)
        entity = await self.asset_repo.get_by_id(asset_id)
        if not entity or entity.warehouse_id != warehouse_id:
            raise NotFoundError("资产记录不存在", code=10001)

        if payload.name is not None:
            entity.name = payload.name.strip()
        if payload.quantity is not None:
            entity.quantity = max(1, int(payload.quantity))
        if payload.unit is not None:
            entity.unit = payload.unit
        if payload.project is not None:
            entity.project = payload.project.strip() or None
        if payload.application is not None:
            entity.application = payload.application.strip() or None
        if payload.category is not None:
            entity.category = payload.category
        if payload.status is not None:
            entity.status = payload.status
        if payload.inbound_at is not None:
            entity.inbound_at = payload.inbound_at
        if payload.outbound_mode is not None:
            entity.outbound_mode = payload.outbound_mode
            if payload.outbound_mode == "undetermined":
                entity.outbound_at = None
        if payload.outbound_at is not None and entity.outbound_mode == "fixed":
            entity.outbound_at = payload.outbound_at
        if payload.owner_name is not None:
            entity.owner_name = payload.owner_name.strip() or None
        if payload.owner_contact is not None:
            entity.owner_contact = payload.owner_contact.strip() or None
        if payload.remark is not None:
            entity.remark = payload.remark

        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        await self.session.refresh(entity)
        return _to_asset_response(entity)

    async def delete_asset(
        self,
        warehouse_id: uuid.UUID,
        asset_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
    ) -> None:
        await self._require_warehouse(warehouse_id)
        entity = await self.asset_repo.get_by_id(asset_id)
        if not entity or entity.warehouse_id != warehouse_id:
            raise NotFoundError("资产记录不存在", code=10001)
        await self.asset_repo.soft_delete(entity, deleted_by=user_id)
