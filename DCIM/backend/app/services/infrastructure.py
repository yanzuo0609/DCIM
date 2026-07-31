from __future__ import annotations

import math
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.device import DeviceStatus
from app.models.infrastructure import Building, DataCenter, Floor, Room
from app.repositories.device import DeviceRepository
from app.repositories.infrastructure import (
    BuildingRepository,
    DataCenterRepository,
    DEFAULT_FLOOR_NAME,
    FloorRepository,
    RoomRepository,
)
from app.repositories.rack import RackPositionRepository, RackRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.infrastructure import (
    BuildingCreate,
    BuildingResponse,
    BuildingUpdate,
    DataCenterCreate,
    DataCenterResponse,
    DataCenterUpdate,
    FloorCreate,
    FloorResponse,
    FloorUpdate,
    RoomCreate,
    RoomQuickCreate,
    RoomResponse,
    RoomUpdate,
    ensure_layout_within_outline,
    expand_row_prefixes,
    generate_slot_codes,
    normalize_room_attributes,
    normalize_row_layout,
    purpose_from_attributes,
    resolve_room_attributes,
)
from app.utils.room_layout import iter_rack_slots



def _to_datacenter_response(entity: DataCenter) -> DataCenterResponse:
    return DataCenterResponse(
        id=str(entity.id),
        code=entity.code,
        name=entity.name,
        location=entity.location,
        description=entity.description,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _to_building_response(entity: Building) -> BuildingResponse:
    return BuildingResponse(
        id=str(entity.id),
        datacenter_id=str(entity.datacenter_id),
        name=entity.name,
        description=entity.description,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _to_floor_response(entity: Floor) -> FloorResponse:
    return FloorResponse(
        id=str(entity.id),
        building_id=str(entity.building_id),
        name=entity.name,
        description=entity.description,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


def _to_room_response(
    entity: Room,
    *,
    rack_count: int = 0,
    used_count: int = 0,
    free_count: int | None = None,
    total_power: float = 0.0,
) -> RoomResponse:
    location = None
    building_no = None
    datacenter_id = None
    datacenter_name = None
    if entity.floor and entity.floor.building:
        building_no = entity.floor.building.name
        if entity.floor.building.datacenter:
            dc = entity.floor.building.datacenter
            location = dc.location or dc.name
            datacenter_id = str(dc.id)
            datacenter_name = dc.name
    row_layout = entity.get_row_layout()
    is_uniform = len(set(row_layout)) <= 1
    capacity = entity.rack_capacity
    used = max(0, int(used_count))
    free = capacity - used if free_count is None else max(0, int(free_count))
    outline_rows = int(getattr(entity, "outline_rows", None) or len(row_layout) or 8)
    outline_cols = int(
        getattr(entity, "outline_cols", None)
        or (max(row_layout) if row_layout else 10)
        or 10
    )
    attributes = resolve_room_attributes(
        entity.attributes if isinstance(getattr(entity, "attributes", None), list) else None,
        purpose=entity.purpose,
    )
    return RoomResponse(
        id=str(entity.id),
        floor_id=str(entity.floor_id),
        name=entity.name,
        datacenter_id=datacenter_id,
        datacenter_name=datacenter_name,
        location=location,
        building_no=building_no,
        room_no=entity.name,
        layout_mode="auto" if is_uniform else "manual",
        rack_rows=len(row_layout),
        rack_columns=max(row_layout) if row_layout else 0,
        row_layout=row_layout,
        outline_rows=outline_rows,
        outline_cols=outline_cols,
        rack_capacity=capacity,
        code_mode=entity.code_mode or "auto",
        code_prefix=entity.code_prefix or "A",
        slot_codes=entity.get_slot_codes(),
        pillar_layout=entity.pillar_layout if isinstance(entity.pillar_layout, dict) else None,
        purpose=entity.purpose or "production",
        importance=entity.importance or "medium",
        attributes=attributes,
        rack_count=max(0, int(rack_count)),
        used_count=used,
        free_count=free,
        total_power=round(float(total_power or 0), 2),
        description=entity.description,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class DataCenterService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = DataCenterRepository(session)
        self.building_repo = BuildingRepository(session)
        self.floor_repo = FloorRepository(session)
        self.room_repo = RoomRepository(session)
        self.rack_repo = RackRepository(session)
        self.position_repo = RackPositionRepository(session)
        self.device_repo = DeviceRepository(session)
        self.session = session

    async def list(self, params: PaginationParams) -> tuple[list[DataCenterResponse], PaginationMeta]:
        items, total = await self.repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort,
            order=params.order,
            search_fields=["code", "name", "location"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [_to_datacenter_response(item) for item in items], pagination

    async def get(self, entity_id: uuid.UUID) -> DataCenterResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Data center not found", code=10001)
        return _to_datacenter_response(entity)

    async def create(
        self, payload: DataCenterCreate, user_id: uuid.UUID | None = None
    ) -> DataCenterResponse:
        existing = await self.repo.get_by_code(payload.code)
        if existing:
            raise ConflictError("Data center code already exists")

        entity = DataCenter(
            code=payload.code,
            name=payload.name,
            location=payload.location,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        return _to_datacenter_response(created)

    async def update(
        self,
        entity_id: uuid.UUID,
        payload: DataCenterUpdate,
        user_id: uuid.UUID | None = None,
    ) -> DataCenterResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Data center not found", code=10001)

        if payload.code and payload.code != entity.code:
            existing = await self.repo.get_by_code(payload.code)
            if existing:
                raise ConflictError("Data center code already exists")
            entity.code = payload.code

        if payload.name is not None:
            entity.name = payload.name
        if payload.location is not None:
            entity.location = payload.location
        if payload.description is not None:
            entity.description = payload.description

        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        await self.session.refresh(entity)
        return _to_datacenter_response(entity)

    async def _cascade_soft_delete_hierarchy(
        self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None
    ) -> dict[str, int]:
        """Soft-delete rooms (and racks), floors, buildings under a datacenter."""
        rooms = await self.room_repo.list_by_datacenter(entity_id)
        rack_count = 0
        device_unmounted = 0
        for room in rooms:
            racks = await self.rack_repo.list_by_room(room.id)
            for rack in racks:
                devices = await self.device_repo.list_by_rack(rack.id)
                for device in devices:
                    device.rack_id = None
                    device.u_position = None
                    device.status = DeviceStatus.STOCK.value
                    device.updated_by = user_id
                    device.version += 1
                    device_unmounted += 1
                positions = await self.position_repo.list_by_rack(rack.id)
                for pos in positions:
                    pos.occupied = False
                    pos.device_id = None
                    pos.updated_by = user_id
                    await self.position_repo.soft_delete(pos, deleted_by=user_id)
                await self.rack_repo.soft_delete(rack, deleted_by=user_id)
                rack_count += 1
            await self.room_repo.soft_delete(room, deleted_by=user_id)

        buildings = await self.building_repo.list_by_datacenter(entity_id)
        building_ids = [b.id for b in buildings]
        floors = await self.floor_repo.list_by_building_ids(building_ids)
        for floor in floors:
            await self.floor_repo.soft_delete(floor, deleted_by=user_id)
        for building in buildings:
            await self.building_repo.soft_delete(building, deleted_by=user_id)

        return {
            "room_count": len(rooms),
            "rack_count": rack_count,
            "device_unmounted": device_unmounted,
            "floor_count": len(floors),
            "building_count": len(buildings),
        }

    async def delete(
        self,
        entity_id: uuid.UUID,
        user_id: uuid.UUID | None = None,
        *,
        force: bool = False,
    ) -> dict[str, int]:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Data center not found", code=10001)

        room_count = await self.room_repo.count_by_datacenter(entity_id)
        if room_count > 0 and not force:
            raise ConflictError(
                f"数据中心下仍有 {room_count} 个机房，无法删除。如需一并清空，请选择强制删除。",
                details={"room_count": room_count, "force_required": True},
            )

        stats = await self._cascade_soft_delete_hierarchy(entity_id, user_id=user_id)
        await self.repo.soft_delete(entity, deleted_by=user_id)
        await self.session.flush()
        return stats


class BuildingService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = BuildingRepository(session)
        self.dc_repo = DataCenterRepository(session)
        self.session = session

    async def list(
        self, params: PaginationParams, datacenter_id: uuid.UUID | None = None
    ) -> tuple[list[BuildingResponse], PaginationMeta]:
        filters = {"datacenter_id": datacenter_id} if datacenter_id else None
        items, total = await self.repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort,
            order=params.order,
            filters=filters,
            search_fields=["name"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [_to_building_response(item) for item in items], pagination

    async def create(
        self, payload: BuildingCreate, user_id: uuid.UUID | None = None
    ) -> BuildingResponse:
        dc_id = uuid.UUID(payload.datacenter_id)
        datacenter = await self.dc_repo.get_by_id(dc_id)
        if not datacenter:
            raise NotFoundError("Data center not found", code=10001)

        existing = await self.repo.get_by_name_in_datacenter(dc_id, payload.name)
        if existing:
            raise ConflictError("Building name already exists in this data center")

        entity = Building(
            datacenter_id=dc_id,
            name=payload.name,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        return _to_building_response(created)

    async def update(
        self,
        entity_id: uuid.UUID,
        payload: BuildingUpdate,
        user_id: uuid.UUID | None = None,
    ) -> BuildingResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Building not found")

        if payload.name and payload.name != entity.name:
            existing = await self.repo.get_by_name_in_datacenter(entity.datacenter_id, payload.name)
            if existing:
                raise ConflictError("Building name already exists in this data center")
            entity.name = payload.name
        if payload.description is not None:
            entity.description = payload.description

        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        await self.session.refresh(entity)
        return _to_building_response(entity)

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Building not found")
        await self.repo.soft_delete(entity, deleted_by=user_id)


class FloorService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = FloorRepository(session)
        self.building_repo = BuildingRepository(session)
        self.session = session

    async def list(
        self, params: PaginationParams, building_id: uuid.UUID | None = None
    ) -> tuple[list[FloorResponse], PaginationMeta]:
        filters = {"building_id": building_id} if building_id else None
        items, total = await self.repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort,
            order=params.order,
            filters=filters,
            search_fields=["name"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [_to_floor_response(item) for item in items], pagination

    async def create(
        self, payload: FloorCreate, user_id: uuid.UUID | None = None
    ) -> FloorResponse:
        building_id = uuid.UUID(payload.building_id)
        building = await self.building_repo.get_by_id(building_id)
        if not building:
            raise NotFoundError("Building not found")

        existing = await self.repo.get_by_name_in_building(building_id, payload.name)
        if existing:
            raise ConflictError("Floor name already exists in this building")

        entity = Floor(
            building_id=building_id,
            name=payload.name,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        return _to_floor_response(created)

    async def update(
        self,
        entity_id: uuid.UUID,
        payload: FloorUpdate,
        user_id: uuid.UUID | None = None,
    ) -> FloorResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Floor not found")

        if payload.name and payload.name != entity.name:
            existing = await self.repo.get_by_name_in_building(entity.building_id, payload.name)
            if existing:
                raise ConflictError("Floor name already exists in this building")
            entity.name = payload.name
        if payload.description is not None:
            entity.description = payload.description

        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        await self.session.refresh(entity)
        return _to_floor_response(entity)

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Floor not found")
        await self.repo.soft_delete(entity, deleted_by=user_id)


class RoomService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = RoomRepository(session)
        self.floor_repo = FloorRepository(session)
        self.building_repo = BuildingRepository(session)
        self.dc_repo = DataCenterRepository(session)
        self.rack_repo = RackRepository(session)
        self.session = session

    async def _enrich_room_responses(self, rooms: list[Room]) -> list[RoomResponse]:
        if not rooms:
            return []
        stats_map = await self.rack_repo.room_stats_for_ids([r.id for r in rooms])
        result: list[RoomResponse] = []
        for room in rooms:
            stats = stats_map.get(room.id) or {}
            rack_count = int(stats.get("rack_count", 0))
            used_count = int(stats.get("used_count", 0))
            capacity = room.rack_capacity
            free_count = max(0, capacity - rack_count)
            result.append(
                _to_room_response(
                    room,
                    rack_count=rack_count,
                    used_count=used_count,
                    free_count=free_count,
                    total_power=float(stats.get("total_power", 0) or 0),
                )
            )
        return result

    async def list(
        self,
        params: PaginationParams,
        floor_id: uuid.UUID | None = None,
        datacenter_id: uuid.UUID | None = None,
    ) -> tuple[list[RoomResponse], PaginationMeta]:
        if datacenter_id is not None:
            items, total = await self.repo.list_paginated_by_datacenter(
                datacenter_id=datacenter_id,
                page=params.page,
                page_size=params.page_size,
                keyword=params.keyword,
                sort=params.sort,
                order=params.order,
            )
        else:
            filters = {"floor_id": floor_id} if floor_id else None
            items, total = await self.repo.list_paginated(
                page=params.page,
                page_size=params.page_size,
                keyword=params.keyword,
                sort=params.sort,
                order=params.order,
                filters=filters,
                search_fields=["name"],
            )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        rooms = await self.repo.list_by_ids_with_hierarchy([item.id for item in items])
        room_map = {r.id: r for r in rooms}
        ordered = [room_map[item.id] for item in items if item.id in room_map]
        return await self._enrich_room_responses(ordered), pagination

    async def get(self, entity_id: uuid.UUID) -> RoomResponse:
        room = await self.repo.get_by_id_with_hierarchy(entity_id)
        if not room:
            raise NotFoundError("Room not found")
        return (await self._enrich_room_responses([room]))[0]

    async def create(self, payload: RoomCreate, user_id: uuid.UUID | None = None) -> RoomResponse:
        floor_id = uuid.UUID(payload.floor_id)
        floor = await self.floor_repo.get_by_id(floor_id)
        if not floor:
            raise NotFoundError("Floor not found")

        existing = await self.repo.get_by_name_in_floor(floor_id, payload.name)
        if existing:
            raise ConflictError("Room name already exists on this floor")

        row_layout = payload.row_layout or [payload.rack_columns] * payload.rack_rows
        slot_codes = payload.slot_codes or generate_slot_codes(
            row_layout,
            code_mode=payload.code_mode,
            code_prefix=payload.code_prefix,
        )
        attributes = normalize_room_attributes(payload.attributes)
        entity = Room(
            floor_id=floor_id,
            name=payload.name,
            description=payload.description,
            purpose=purpose_from_attributes(attributes) if attributes else (payload.purpose or "other"),
            importance=payload.importance or "medium",
            attributes=attributes,
            outline_rows=payload.outline_rows,
            outline_cols=payload.outline_cols,
            rack_rows=len(row_layout),
            rack_columns=max(row_layout),
            row_layout=row_layout,
            code_mode=payload.code_mode,
            code_prefix=payload.code_prefix or "A",
            slot_codes=slot_codes,
            pillar_layout=payload.pillar_layout if isinstance(payload.pillar_layout, dict) else None,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        room = await self.repo.get_by_id_with_hierarchy(created.id)
        assert room is not None
        return (await self._enrich_room_responses([room]))[0]

    async def create_quick(
        self, payload: RoomQuickCreate, user_id: uuid.UUID | None = None
    ) -> RoomResponse:
        datacenter = await self.dc_repo.get_by_id(uuid.UUID(payload.datacenter_id))
        if not datacenter:
            raise NotFoundError("Data center not found", code=10001)

        building_no = payload.building_no.strip()
        room_no = payload.room_no.strip()
        row_layout = payload.row_layout or [payload.rack_columns] * payload.rack_rows
        slot_codes = payload.slot_codes or generate_slot_codes(
            row_layout,
            code_mode=payload.code_mode,
            code_prefix=payload.code_prefix,
        )
        attributes = normalize_room_attributes(payload.attributes)

        building = await self.building_repo.get_by_name_in_datacenter(datacenter.id, building_no)
        if not building:
            building = Building(
                datacenter_id=datacenter.id,
                name=building_no,
                created_by=user_id,
                updated_by=user_id,
            )
            building = await self.building_repo.create(building)

        floor = await self.floor_repo.get_by_name_in_building(building.id, DEFAULT_FLOOR_NAME)
        if not floor:
            floor = Floor(
                building_id=building.id,
                name=DEFAULT_FLOOR_NAME,
                created_by=user_id,
                updated_by=user_id,
            )
            floor = await self.floor_repo.create(floor)

        existing = await self.repo.get_by_name_in_floor(floor.id, room_no)
        if existing:
            raise ConflictError("Room number already exists in this building")

        entity = Room(
            floor_id=floor.id,
            name=room_no,
            description=payload.description,
            purpose=purpose_from_attributes(attributes) if attributes else (payload.purpose or "other"),
            importance=payload.importance or "medium",
            attributes=attributes,
            outline_rows=payload.outline_rows,
            outline_cols=payload.outline_cols,
            rack_rows=len(row_layout),
            rack_columns=max(row_layout),
            row_layout=row_layout,
            code_mode=payload.code_mode,
            code_prefix=payload.code_prefix or "A",
            slot_codes=slot_codes,
            pillar_layout=payload.pillar_layout if isinstance(payload.pillar_layout, dict) else None,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        room = await self.repo.get_by_id_with_hierarchy(created.id)
        assert room is not None
        return (await self._enrich_room_responses([room]))[0]

    async def update(
        self,
        entity_id: uuid.UUID,
        payload: RoomUpdate,
        user_id: uuid.UUID | None = None,
    ) -> RoomResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Room not found")

        new_name = payload.room_no or payload.name
        if new_name and new_name != entity.name:
            existing = await self.repo.get_by_name_in_floor(entity.floor_id, new_name)
            if existing:
                raise ConflictError("Room name already exists on this floor")
            entity.name = new_name
        if payload.description is not None:
            entity.description = payload.description
        if payload.importance is not None:
            entity.importance = payload.importance
        if payload.attributes is not None:
            try:
                attrs = normalize_room_attributes(payload.attributes)
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc
            entity.attributes = attrs
            entity.purpose = purpose_from_attributes(attrs)
        elif payload.purpose is not None:
            entity.purpose = payload.purpose

        if payload.outline_rows is not None:
            entity.outline_rows = payload.outline_rows
        if payload.outline_cols is not None:
            entity.outline_cols = payload.outline_cols

        layout_changed = (
            payload.layout_mode is not None
            or payload.row_layout is not None
            or payload.rack_rows is not None
            or payload.rack_columns is not None
        )
        outline_changed = payload.outline_rows is not None or payload.outline_cols is not None
        code_changed = (
            payload.code_mode is not None
            or payload.code_prefix is not None
            or payload.slot_codes is not None
        )
        new_layout: list[int] | None = None
        if layout_changed:
            try:
                if payload.layout_mode == "manual" or (
                    payload.row_layout is not None and payload.layout_mode != "auto"
                ):
                    new_layout = normalize_row_layout(
                        layout_mode="manual",
                        row_layout=payload.row_layout or entity.get_row_layout(),
                    )
                else:
                    new_layout = normalize_row_layout(
                        layout_mode="auto",
                        rack_rows=payload.rack_rows or len(entity.get_row_layout()),
                        rack_columns=payload.rack_columns
                        or (max(entity.get_row_layout()) if entity.get_row_layout() else 6),
                        row_layout=payload.row_layout,
                    )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

            entity.row_layout = new_layout
            entity.rack_rows = len(new_layout)
            entity.rack_columns = max(new_layout)

        if layout_changed or outline_changed:
            try:
                ensure_layout_within_outline(
                    entity.get_row_layout(),
                    outline_rows=int(entity.outline_rows or 8),
                    outline_cols=int(entity.outline_cols or 10),
                )
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        pending_slot_codes: list[list[str]] | None = None
        if layout_changed or code_changed:
            try:
                code_mode = payload.code_mode or entity.code_mode or "auto"
                code_prefix = (
                    payload.code_prefix
                    if payload.code_prefix is not None
                    else (entity.code_prefix or "A")
                )
                pending_slot_codes = generate_slot_codes(
                    entity.get_row_layout(),
                    code_mode=code_mode,  # type: ignore[arg-type]
                    code_prefix=code_prefix,
                    slot_codes=payload.slot_codes if code_mode == "custom" else None,
                )
                entity.slot_codes = pending_slot_codes
                entity.code_mode = code_mode
                entity.code_prefix = code_prefix
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        if payload.pillar_layout is not None:
            mode = payload.pillar_layout.get("mode") or "grid"
            if mode not in ("auto_middle", "cells", "grid"):
                raise ValidationError("pillar_layout.mode must be auto_middle, cells or grid")
            cells = payload.pillar_layout.get("cells") or {}
            if cells is not None and not isinstance(cells, dict):
                raise ValidationError("pillar_layout.cells must be an object")
            rows = payload.pillar_layout.get("rows")
            cols = payload.pillar_layout.get("cols")
            stored: dict = {"mode": mode, "cells": cells}
            if rows is not None:
                try:
                    stored["rows"] = max(1, min(50, int(rows)))
                except (TypeError, ValueError) as exc:
                    raise ValidationError("pillar_layout.rows must be an integer") from exc
            if cols is not None:
                try:
                    stored["cols"] = max(1, min(50, int(cols)))
                except (TypeError, ValueError) as exc:
                    raise ValidationError("pillar_layout.cols must be an integer") from exc
            entity.pillar_layout = stored

        # 布局 / 编号 / 立柱变更后：机柜位不足时自动补齐，再重排已有机柜
        if layout_changed or code_changed or payload.pillar_layout is not None:
            await self._ensure_layout_fits_existing_racks(entity)
            await self._reposition_racks_for_layout(
                entity.id,
                entity.get_row_layout(),
                entity.slot_codes if isinstance(entity.slot_codes, list) else None,
                entity.pillar_layout if isinstance(entity.pillar_layout, dict) else None,
                code_mode=entity.code_mode or "auto",
            )

        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        room = await self.repo.get_by_id_with_hierarchy(entity_id)
        assert room is not None
        return (await self._enrich_room_responses([room]))[0]

    @staticmethod
    def _collect_rack_slots(
        row_layout: list[int],
        slot_codes: list[list[str]] | None,
        pillar_layout: dict | None,
        *,
        code_mode: str | None = None,
    ) -> list[tuple[int, int, str]]:
        return iter_rack_slots(
            row_layout,
            slot_codes,
            pillar_layout,
            code_mode=code_mode,
        )

    async def _ensure_layout_fits_existing_racks(self, entity: Room) -> int:
        """机柜位不足时在各排尾部自动补机柜格（保留立柱），返回补齐数量。"""
        racks = await self.rack_repo.list_by_room(entity.id)
        if not racks:
            return 0

        row_layout = list(entity.get_row_layout())
        if not row_layout:
            row_layout = [max(1, len(racks))]

        slot_codes: list[list[str]]
        if isinstance(entity.slot_codes, list) and entity.slot_codes:
            slot_codes = [
                [str(c or "") for c in (row if isinstance(row, list) else [])]
                for row in entity.slot_codes
            ]
        else:
            slot_codes = generate_slot_codes(
                row_layout,
                code_mode="auto",
                code_prefix=entity.code_prefix or "A",
            )

        pillar_layout = (
            dict(entity.pillar_layout) if isinstance(entity.pillar_layout, dict) else {"mode": "cells", "cells": {}}
        )
        cells_raw = pillar_layout.get("cells") if isinstance(pillar_layout.get("cells"), dict) else {}
        cells: dict[str, list] = {
            str(k): list(v) if isinstance(v, list) else [] for k, v in cells_raw.items()
        }

        # 对齐行列长度
        while len(slot_codes) < len(row_layout):
            slot_codes.append([])
        slot_codes = slot_codes[: len(row_layout)]
        for i, cols in enumerate(row_layout):
            row_codes = slot_codes[i]
            if len(row_codes) < cols:
                row_codes.extend([""] * (cols - len(row_codes)))
            else:
                slot_codes[i] = row_codes[:cols]
            key = str(i + 1)
            if key in cells:
                kinds = cells[key]
                if len(kinds) < cols:
                    kinds.extend(["rack"] * (cols - len(kinds)))
                else:
                    cells[key] = kinds[:cols]

        slots = self._collect_rack_slots(
            row_layout,
            slot_codes,
            {**pillar_layout, "cells": cells},
            code_mode=entity.code_mode or "auto",
        )
        deficit = len(racks) - len(slots)
        if deficit <= 0:
            return 0

        code_prefix = entity.code_prefix or "A"
        added = 0
        # 轮询在各排尾部补机柜格，支持不等长排 + 立柱占位
        while deficit > 0:
            row_idx = added % len(row_layout)
            if row_layout[row_idx] >= 50:
                # 该排已满则找下一排
                progressed = False
                for offset in range(len(row_layout)):
                    cand = (row_idx + offset) % len(row_layout)
                    if row_layout[cand] < 50:
                        row_idx = cand
                        progressed = True
                        break
                if not progressed:
                    raise ValidationError(
                        f"机房已有 {len(racks)} 台机柜，但布局无法继续扩容（每排最多 50 格）。"
                        f"请增加排数或先删除多余机柜后再保存",
                        code=10004,
                    )

            row_layout[row_idx] += 1
            key = str(row_idx + 1)
            if cells:
                kinds = cells.setdefault(key, ["rack"] * (row_layout[row_idx] - 1))
                while len(kinds) < row_layout[row_idx] - 1:
                    kinds.append("rack")
                kinds.append("rack")
                cells[key] = kinds

            # 为新格生成编号（跳过立柱后的下一序号）
            row_codes = slot_codes[row_idx]
            while len(row_codes) < row_layout[row_idx] - 1:
                row_codes.append("")
            existing_codes = [c.strip() for c in row_codes if str(c or "").strip()]
            try:
                prefixes = expand_row_prefixes(code_prefix, len(row_layout))
                prefix = prefixes[row_idx]
            except Exception:
                prefix = "R"
            seq = len(existing_codes) + 1
            width = max(2, len(str(max(seq, row_layout[row_idx]))))
            new_code = f"{prefix}{seq:0{width}d}"
            # 避免冲突
            used = {c.lower() for c in existing_codes}
            while new_code.lower() in used:
                seq += 1
                new_code = f"{prefix}{seq:0{width}d}"
            row_codes.append(new_code)
            slot_codes[row_idx] = row_codes
            added += 1
            deficit -= 1

        entity.row_layout = row_layout
        entity.rack_rows = len(row_layout)
        entity.rack_columns = max(row_layout) if row_layout else 0
        entity.slot_codes = slot_codes
        entity.code_mode = entity.code_mode or "custom"
        if entity.code_mode == "auto" and cells:
            entity.code_mode = "custom"
        if cells:
            pillar_layout["mode"] = pillar_layout.get("mode") or "cells"
            pillar_layout["cells"] = cells
            pillar_layout["rows"] = len(row_layout)
            pillar_layout["cols"] = max(row_layout) if row_layout else 0
            entity.pillar_layout = pillar_layout
        return added

    async def _reposition_racks_for_layout(
        self,
        room_id: uuid.UUID,
        row_layout: list[int],
        slot_codes: list[list[str]] | None,
        pillar_layout: dict | None,
        *,
        code_mode: str | None = None,
    ) -> None:
        """将已有机柜适配到新布局的有效机柜位（可跨排）。"""
        racks = await self.rack_repo.list_by_room(room_id)
        if not racks:
            return

        slots = self._collect_rack_slots(
            row_layout, slot_codes, pillar_layout, code_mode=code_mode
        )
        if len(racks) > len(slots):
            raise ValidationError(
                f"机房已有 {len(racks)} 台机柜，但当前编号/立柱布局仅有 {len(slots)} 个机柜位。"
                f"请增加编号格、减少立柱，或先删除多余机柜后再保存",
                code=10004,
            )

        slot_keys = {(r, c) for r, c, _ in slots}
        slot_code_map = {(r, c): code for r, c, code in slots}
        racks_sorted = sorted(racks, key=lambda r: (int(r.row_no), int(r.column_no), r.code or ""))

        occupied: set[tuple[int, int]] = set()
        unassigned: list = []
        for rack in racks_sorted:
            pos = (int(rack.row_no), int(rack.column_no))
            if pos in slot_keys and pos not in occupied:
                occupied.add(pos)
            else:
                unassigned.append(rack)

        free_slots = [s for s in slots if (s[0], s[1]) not in occupied]
        if len(unassigned) > len(free_slots):
            raise ValidationError(
                f"机房已有 {len(racks)} 台机柜，但当前编号/立柱布局仅有 {len(slots)} 个机柜位。"
                f"请增加编号格、减少立柱，或先删除多余机柜后再保存",
                code=10004,
            )

        for rack, (row_no, col_no, _code) in zip(unassigned, free_slots):
            rack.row_no = row_no
            rack.column_no = col_no
            occupied.add((row_no, col_no))

        for rack in racks_sorted:
            pos = (int(rack.row_no), int(rack.column_no))
            code = slot_code_map.get(pos) or ""
            if not code:
                continue
            conflict = await self.rack_repo.get_by_code_in_room(room_id, code)
            if conflict is None or conflict.id == rack.id:
                rack.code = code

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Room not found")
        await self.repo.soft_delete(entity, deleted_by=user_id)
