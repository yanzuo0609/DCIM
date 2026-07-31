import math
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.infrastructure import Building, DataCenter, Floor, Room
from app.repositories.infrastructure import (
    BuildingRepository,
    DataCenterRepository,
    DEFAULT_FLOOR_NAME,
    FloorRepository,
    RoomRepository,
)
from app.repositories.rack import RackRepository
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
    generate_slot_codes,
    normalize_row_layout,
)


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


def _to_room_response(entity: Room) -> RoomResponse:
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
        rack_capacity=sum(row_layout),
        code_mode=entity.code_mode or "auto",
        code_prefix=entity.code_prefix or "A",
        slot_codes=entity.get_slot_codes(),
        description=entity.description,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
    )


class DataCenterService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = DataCenterRepository(session)
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

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Data center not found", code=10001)
        await self.repo.soft_delete(entity, deleted_by=user_id)


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

    async def list(
        self, params: PaginationParams, floor_id: uuid.UUID | None = None
    ) -> tuple[list[RoomResponse], PaginationMeta]:
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
        enriched = [
            _to_room_response(room_map[item.id]) for item in items if item.id in room_map
        ]
        return enriched, pagination

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
        entity = Room(
            floor_id=floor_id,
            name=payload.name,
            description=payload.description,
            rack_rows=len(row_layout),
            rack_columns=max(row_layout),
            row_layout=row_layout,
            code_mode=payload.code_mode,
            code_prefix=payload.code_prefix or "A",
            slot_codes=slot_codes,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        room = await self.repo.get_by_id_with_hierarchy(created.id)
        assert room is not None
        return _to_room_response(room)

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
            rack_rows=len(row_layout),
            rack_columns=max(row_layout),
            row_layout=row_layout,
            code_mode=payload.code_mode,
            code_prefix=payload.code_prefix or "A",
            slot_codes=slot_codes,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        room = await self.repo.get_by_id_with_hierarchy(created.id)
        assert room is not None
        return _to_room_response(room)

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

        layout_changed = (
            payload.layout_mode is not None
            or payload.row_layout is not None
            or payload.rack_rows is not None
            or payload.rack_columns is not None
        )
        code_changed = (
            payload.code_mode is not None
            or payload.code_prefix is not None
            or payload.slot_codes is not None
        )
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

            racks = await self.rack_repo.list_by_room(entity.id)
            for rack in racks:
                if rack.row_no > len(new_layout) or rack.column_no > new_layout[rack.row_no - 1]:
                    raise ValidationError(
                        "Cannot shrink rack layout below existing rack positions",
                        code=10004,
                    )
            entity.row_layout = new_layout
            entity.rack_rows = len(new_layout)
            entity.rack_columns = max(new_layout)

        if layout_changed or code_changed:
            try:
                code_mode = payload.code_mode or entity.code_mode or "auto"
                code_prefix = (
                    payload.code_prefix
                    if payload.code_prefix is not None
                    else (entity.code_prefix or "A")
                )
                entity.slot_codes = generate_slot_codes(
                    entity.get_row_layout(),
                    code_mode=code_mode,  # type: ignore[arg-type]
                    code_prefix=code_prefix,
                    slot_codes=payload.slot_codes if code_mode == "custom" else None,
                )
                entity.code_mode = code_mode
                entity.code_prefix = code_prefix
            except ValueError as exc:
                raise ValidationError(str(exc)) from exc

        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        room = await self.repo.get_by_id_with_hierarchy(entity_id)
        assert room is not None
        return _to_room_response(room)

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Room not found")
        await self.repo.soft_delete(entity, deleted_by=user_id)
