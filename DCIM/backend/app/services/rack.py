import math
import re
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.models.infrastructure import Room
from app.models.rack import Rack, RackPosition, RackTemplate
from app.repositories.device import DeviceRepository
from app.repositories.infrastructure import RoomRepository
from app.repositories.rack import RackPositionRepository, RackRepository, RackTemplateRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.rack import (
    ApplyTemplateToRoomRequest,
    ApplyTemplateToRoomResult,
    PlaceBatchRequest,
    PlaceBatchResult,
    RackBatchDeleteRequest,
    RackBatchDeleteResult,
    RackCodeCheckResponse,
    RackCodeConflictInfo,
    RackCreate,
    RackLayoutDevice,
    RackLayoutResponse,
    RackLayoutSlot,
    RackPositionResponse,
    RackResponse,
    RackTemplateAppliedRoom,
    RackTemplateCreate,
    RackTemplateResponse,
    RackTemplateUpdate,
    RackUpdate,
    UnapplyTemplateFromRoomRequest,
    UnapplyTemplateFromRoomResult,
)

_IPV4_RE = re.compile(r"\b(?:(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\.){3}(?:25[0-5]|2[0-4]\d|[01]?\d\d?)\b")


def _as_uuid(value: str | uuid.UUID) -> uuid.UUID:
    """Parse dashed / undashed UUID strings safely."""
    if isinstance(value, uuid.UUID):
        return value
    text = (value or "").strip()
    if not text:
        raise ValueError("empty uuid")
    return uuid.UUID(text)


def _uuid_str(value: str | uuid.UUID) -> str:
    return str(_as_uuid(value))


async def _require_active_room(room_repo: RoomRepository, room_id_raw: str | uuid.UUID):
    try:
        room_id = _as_uuid(room_id_raw)
    except ValueError as exc:
        raise ValidationError("机房 ID 格式无效", code=10004) from exc
    room = await room_repo.get_by_id(room_id)
    if not room:
        raise NotFoundError("机房不存在或已删除", code=10001)
    return room_id, room


def _extract_ip_fields(device) -> tuple[str | None, str | None, str | None]:
    """Return (system_ip, bmc_ip, vip) from device.ip_addresses."""
    rows = list(getattr(device, "ip_addresses", None) or [])
    if rows:
        primary = rows[0]
        for row in rows:
            if getattr(row, "system_ip", None):
                primary = row
                break
        return primary.system_ip, primary.bmc_ip, primary.vip
    hostname = (device.hostname or "").strip()
    if hostname and _IPV4_RE.fullmatch(hostname):
        return hostname, None, None
    description = device.description
    if description:
        match = _IPV4_RE.search(description)
        if match:
            return match.group(0), None, None
    return None, None, None


def _rack_stats(rack: Rack) -> tuple[int, int, float, int]:
    occupied = sum(1 for pos in rack.positions if pos.occupied)
    free = rack.total_u - occupied
    utilization = round((occupied / rack.total_u) * 100, 2) if rack.total_u else 0.0
    device_ids = {pos.device_id for pos in rack.positions if pos.occupied and pos.device_id}
    return occupied, free, utilization, len(device_ids)


def _to_rack_response(
    rack: Rack,
    *,
    occupied_u: int | None = None,
    device_count: int | None = None,
) -> RackResponse:
    if occupied_u is None or device_count is None:
        occupied, free, utilization, dcount = _rack_stats(rack)
    else:
        occupied = occupied_u
        free = max(rack.total_u - occupied, 0)
        utilization = round((occupied / rack.total_u) * 100, 2) if rack.total_u else 0.0
        dcount = device_count
    return RackResponse(
        id=str(rack.id),
        room_id=str(rack.room_id),
        rack_template_id=str(rack.rack_template_id) if rack.rack_template_id else None,
        code=rack.code,
        name=rack.name,
        row_no=rack.row_no,
        column_no=rack.column_no,
        total_u=rack.total_u,
        width=rack.width,
        depth=rack.depth,
        status=rack.status,
        description=rack.description,
        occupied_u=occupied,
        free_u=free,
        utilization=utilization,
        device_count=dcount,
        created_at=rack.created_at,
        updated_at=rack.updated_at,
    )


def _to_position_response(position: RackPosition) -> RackPositionResponse:
    return RackPositionResponse(
        id=str(position.id),
        rack_id=str(position.rack_id),
        u_position=position.u_position,
        occupied=position.occupied,
        device_id=str(position.device_id) if position.device_id else None,
    )


def _to_template_response(
    entity: RackTemplate,
    *,
    applied_rooms: list[RackTemplateAppliedRoom] | None = None,
) -> RackTemplateResponse:
    rooms = applied_rooms or []
    return RackTemplateResponse(
        id=str(entity.id),
        code=entity.code,
        name=entity.name,
        total_u=entity.total_u,
        width=entity.width,
        depth=entity.depth,
        description=entity.description,
        created_at=entity.created_at,
        updated_at=entity.updated_at,
        applied_rack_count=sum(r.rack_count for r in rooms),
        applied_rooms=rooms,
    )


async def _init_rack_positions(
    session: AsyncSession,
    rack: Rack,
    user_id: uuid.UUID | None = None,
) -> None:
    for u in range(1, rack.total_u + 1):
        session.add(
            RackPosition(
                rack_id=rack.id,
                u_position=u,
                occupied=False,
                created_by=user_id,
                updated_by=user_id,
            )
        )
        await session.flush()


def _resolve_rack_position(
    room,
    existing_racks: list[Rack],
    row_no: int | None,
    column_no: int | None,
) -> tuple[int, int]:
    occupied = {(rack.row_no, rack.column_no) for rack in existing_racks}
    row_layout = room.get_row_layout()

    if row_no is not None and column_no is not None:
        if row_no < 1 or row_no > len(row_layout) or column_no < 1 or column_no > row_layout[row_no - 1]:
            raise ValidationError(
                f"Position exceeds room layout (row {row_no} has {row_layout[row_no - 1] if 1 <= row_no <= len(row_layout) else 0} racks)",
                code=10004,
            )
        if (row_no, column_no) in occupied:
            raise ConflictError("Rack position already occupied", code=10002)
        return row_no, column_no

    for r, cols in enumerate(row_layout, start=1):
        for c in range(1, cols + 1):
            if (r, c) not in occupied:
                return r, c

    raise ConflictError("No available rack slots in this room", code=10002)


async def _free_soft_deleted_slot_identity(
    repo: RackRepository,
    room_id: uuid.UUID,
    slot_code: str,
) -> None:
    """Rename soft-deleted holders so the room slot number can be reused exactly."""
    holders = await repo.list_soft_deleted_holding_identity(room_id, slot_code)
    for rack in holders:
        suffix = rack.id.hex[:8]
        rack.code = f"{slot_code}__del_{suffix}"
        rack.name = f"{slot_code}__del_{suffix}"
    if holders:
        await repo.session.flush()


async def _slot_identity(
    repo: RackRepository,
    room_id: uuid.UUID,
    slot_code: str,
    *,
    exclude_id: uuid.UUID | None = None,
) -> tuple[str, str]:
    """Use room rack number as both code and name — no room prefix / serial suffix."""
    identity = (slot_code or "").strip()
    if not identity:
        raise ValidationError("机柜编号不能为空", code=10004)
    # Auto layout codes are like A01/B10; reject bare letters (e.g. "A") as garbage.
    if not re.search(r"\d", identity):
        raise ValidationError(
            f"机柜编号「{identity}」无效，须包含数字序号（如 A01）",
            code=10004,
        )

    await _free_soft_deleted_slot_identity(repo, room_id, identity)

    existing_code = await repo.get_by_code_in_room(room_id, identity, active_only=True)
    if existing_code and (exclude_id is None or existing_code.id != exclude_id):
        raise ConflictError(
            f"机柜编号「{identity}」已被占用"
            f"（位置 R{existing_code.row_no}-C{existing_code.column_no}）",
            code=10002,
            details={
                "field": "code",
                "conflict": _conflict_info(existing_code).model_dump(),
            },
        )

    existing_name = await repo.get_by_name_in_room(room_id, identity)
    if existing_name and (exclude_id is None or existing_name.id != exclude_id):
        raise ConflictError(
            f"机柜名称「{identity}」已被占用"
            f"（编码：{existing_name.code}，位置 R{existing_name.row_no}-C{existing_name.column_no}）",
            code=10002,
            details={
                "field": "name",
                "conflict": _conflict_info(existing_name).model_dump(),
            },
        )

    # Soft-deleted may still hold name/code after free; ensure uniqueness indexes are clear.
    if await repo.code_exists_in_room(room_id, identity, exclude_id=exclude_id):
        await _free_soft_deleted_slot_identity(repo, room_id, identity)
    if await repo.name_exists_in_room(room_id, identity, exclude_id=exclude_id):
        await _free_soft_deleted_slot_identity(repo, room_id, identity)

    return identity, identity


def _conflict_info(rack: Rack, room_name: str | None = None) -> RackCodeConflictInfo:
    return RackCodeConflictInfo(
        id=str(rack.id),
        code=rack.code,
        name=rack.name,
        room_id=str(rack.room_id),
        room_name=room_name,
        row_no=rack.row_no,
        column_no=rack.column_no,
    )


class RackTemplateService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = RackTemplateRepository(session)
        self.rack_repo = RackRepository(session)
        self.room_repo = RoomRepository(session)
        self.position_repo = RackPositionRepository(session)
        self.session = session

    async def _usage_map(
        self, template_ids: list[uuid.UUID]
    ) -> dict[uuid.UUID, list[RackTemplateAppliedRoom]]:
        if not template_ids:
            return {}
        rows = await self.rack_repo.template_usage_rows(template_ids)
        room_ids = list({room_id for _, room_id, _ in rows})
        room_meta: dict[uuid.UUID, tuple[str, bool]] = {}
        if room_ids:
            # Include soft-deleted rooms so usage labels stay human-readable.
            room_result = await self.session.execute(select(Room).where(Room.id.in_(room_ids)))
            for room in room_result.scalars().all():
                room_meta[room.id] = (room.name, room.deleted_at is not None)

        usage: dict[uuid.UUID, list[RackTemplateAppliedRoom]] = {tid: [] for tid in template_ids}
        for template_id, room_id, count in rows:
            name, deleted = room_meta.get(room_id, (None, False))
            if name:
                display_name = f"{name}（已删除）" if deleted else name
            else:
                display_name = f"未知机房（{_uuid_str(room_id)[:8]}…）"
                deleted = True
            usage.setdefault(template_id, []).append(
                RackTemplateAppliedRoom(
                    id=_uuid_str(room_id),
                    name=display_name,
                    rack_count=count,
                    room_deleted=deleted,
                )
            )
        for rooms in usage.values():
            rooms.sort(key=lambda r: (r.room_deleted, r.name))
        return usage

    async def list(
        self, params: PaginationParams
    ) -> tuple[list[RackTemplateResponse], PaginationMeta]:
        items, total = await self.repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort,
            order=params.order,
            search_fields=["code", "name"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        usage = await self._usage_map([item.id for item in items])
        return [
            _to_template_response(item, applied_rooms=usage.get(item.id, []))
            for item in items
        ], pagination

    async def create(
        self, payload: RackTemplateCreate, user_id: uuid.UUID | None = None
    ) -> RackTemplateResponse:
        if await self.repo.get_by_code(payload.code):
            raise ConflictError("Rack template code already exists")
        entity = RackTemplate(
            code=payload.code,
            name=payload.name,
            total_u=payload.total_u,
            width=payload.width,
            depth=payload.depth,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        return _to_template_response(created)

    async def update(
        self,
        entity_id: uuid.UUID,
        payload: RackTemplateUpdate,
        user_id: uuid.UUID | None = None,
    ) -> RackTemplateResponse:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Rack template not found")
        if payload.name is not None:
            entity.name = payload.name
        if payload.total_u is not None:
            entity.total_u = payload.total_u
        if payload.width is not None:
            entity.width = payload.width
        if payload.depth is not None:
            entity.depth = payload.depth
        if payload.description is not None:
            entity.description = payload.description
        entity.updated_by = user_id
        entity.version += 1
        await self.session.flush()
        await self.session.refresh(entity)
        usage = await self._usage_map([entity.id])
        return _to_template_response(entity, applied_rooms=usage.get(entity.id, []))

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        entity = await self.repo.get_by_id(entity_id)
        if not entity:
            raise NotFoundError("Rack template not found")
        await self.repo.soft_delete(entity, deleted_by=user_id)

    async def apply_to_room(
        self,
        template_id: uuid.UUID,
        payload: ApplyTemplateToRoomRequest,
        user_id: uuid.UUID | None = None,
    ) -> ApplyTemplateToRoomResult:
        template = await self.repo.get_by_id(template_id)
        if not template:
            raise NotFoundError("机柜样式模板不存在", code=10001)

        room_id, room = await _require_active_room(self.room_repo, payload.room_id)

        result = ApplyTemplateToRoomResult()
        existing_racks = await self.rack_repo.list_by_room(room_id)

        for rack in existing_racks:
            full = await self.rack_repo.get_by_id_with_positions(rack.id)
            if not full:
                continue
            try:
                if full.total_u != template.total_u:
                    await self._resize_positions(full, template.total_u, user_id)
                    full.total_u = template.total_u
                full.width = template.width
                full.depth = template.depth
                full.rack_template_id = template.id
                full.updated_by = user_id
                full.version += 1
                result.updated += 1
            except Exception as exc:  # noqa: BLE001
                result.skipped += 1
                result.errors.append(f"{full.code}: {exc}")

        await self.session.flush()

        if payload.fill_empty_slots:
            occupied = {(r.row_no, r.column_no) for r in await self.rack_repo.list_by_room(room_id)}
            row_layout = room.get_row_layout()
            codes = room.get_slot_codes()
            for row_idx, cols in enumerate(row_layout):
                row_no = row_idx + 1
                for col_no in range(1, cols + 1):
                    if (row_no, col_no) in occupied:
                        continue
                    slot_code = (
                        codes[row_idx][col_no - 1]
                        if row_idx < len(codes) and col_no - 1 < len(codes[row_idx])
                        else f"R{row_no:02d}{col_no:02d}"
                    )
                    try:
                        code, name = await _slot_identity(self.rack_repo, room_id, slot_code)
                        entity = Rack(
                            room_id=room_id,
                            rack_template_id=template.id,
                            code=code,
                            name=name,
                            row_no=row_no,
                            column_no=col_no,
                            total_u=template.total_u,
                            width=template.width,
                            depth=template.depth,
                            status="active",
                            created_by=user_id,
                            updated_by=user_id,
                        )
                        created = await self.rack_repo.create(entity)
                        await _init_rack_positions(self.session, created, user_id)
                        result.created += 1
                    except ConflictError as exc:
                        result.skipped += 1
                        result.errors.append(f"R{row_no}-C{col_no}: {exc.message}")
                    except Exception as exc:  # noqa: BLE001
                        result.skipped += 1
                        result.errors.append(f"R{row_no}-C{col_no}: {exc}")

        await self.session.flush()
        return result

    async def unapply_from_room(
        self,
        template_id: uuid.UUID,
        payload: UnapplyTemplateFromRoomRequest,
        user_id: uuid.UUID | None = None,
    ) -> UnapplyTemplateFromRoomResult:
        template = await self.repo.get_by_id(template_id)
        if not template:
            raise NotFoundError("机柜样式模板不存在", code=10001)

        try:
            room_id = _as_uuid(payload.room_id)
        except ValueError as exc:
            raise ValidationError("机房 ID 格式无效", code=10004) from exc

        # Allow unapply even if the room was soft-deleted; racks may still reference it.
        room = await self.session.get(Room, room_id)
        racks = await self.rack_repo.list_by_room_and_template(room_id, template_id)
        if not racks:
            if room is None:
                raise NotFoundError("机房不存在，且没有绑定该模板的机柜", code=10001)
            return UnapplyTemplateFromRoomResult()

        if not payload.delete_empty_racks and not payload.detach_template:
            raise ValidationError(
                "请至少选择「删除空机柜」或「解除模板关联」之一",
                code=10004,
            )

        result = UnapplyTemplateFromRoomResult()
        for rack in racks:
            full = await self.rack_repo.get_by_id_with_positions(rack.id)
            if not full:
                continue
            has_devices = any(pos.occupied for pos in full.positions)
            try:
                if payload.delete_empty_racks and not has_devices:
                    await self.rack_repo.soft_delete(full, deleted_by=user_id)
                    result.deleted += 1
                    continue
                if payload.detach_template:
                    full.rack_template_id = None
                    full.updated_by = user_id
                    full.version += 1
                    result.detached += 1
                else:
                    result.skipped += 1
                    result.errors.append(f"{full.code}: 有设备占用，未删除且未解除关联")
            except Exception as exc:  # noqa: BLE001
                result.skipped += 1
                result.errors.append(f"{full.code}: {exc}")

        await self.session.flush()
        return result

    async def _resize_positions(
        self,
        rack: Rack,
        new_total_u: int,
        user_id: uuid.UUID | None,
    ) -> None:
        if new_total_u < rack.total_u:
            positions_to_remove = [p for p in rack.positions if p.u_position > new_total_u]
            for pos in positions_to_remove:
                if pos.occupied:
                    raise ValidationError(
                        "Cannot reduce rack U count while upper positions are occupied",
                        code=10004,
                    )
                await self.position_repo.soft_delete(pos, deleted_by=user_id)
        elif new_total_u > rack.total_u:
            existing = {p.u_position for p in rack.positions}
            for u in range(rack.total_u + 1, new_total_u + 1):
                if u not in existing:
                    self.session.add(
                        RackPosition(
                            rack_id=rack.id,
                            u_position=u,
                            occupied=False,
                            created_by=user_id,
                            updated_by=user_id,
                        )
                    )
            await self.session.flush()


class RackService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = RackRepository(session)
        self.room_repo = RoomRepository(session)
        self.template_repo = RackTemplateRepository(session)
        self.position_repo = RackPositionRepository(session)
        self.device_repo = DeviceRepository(session)
        self.session = session

    async def list(
        self, params: PaginationParams, room_id: uuid.UUID | None = None
    ) -> tuple[list[RackResponse], PaginationMeta]:
        filters = {"room_id": room_id} if room_id else None
        items, total = await self.repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort,
            order=params.order,
            filters=filters,
            search_fields=["code", "name"],
        )
        stats = await self.position_repo.stats_for_rack_ids([item.id for item in items])
        enriched = [
            _to_rack_response(
                item,
                occupied_u=stats.get(item.id, (0, 0))[0],
                device_count=stats.get(item.id, (0, 0))[1],
            )
            for item in items
        ]
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return enriched, pagination

    async def get(self, entity_id: uuid.UUID) -> RackResponse:
        rack = await self.repo.get_by_id_with_positions(entity_id)
        if not rack:
            raise NotFoundError("Rack not found", code=10001)
        return _to_rack_response(rack)

    async def check_code(
        self, code: str, room_id: uuid.UUID | None = None, preferred_base: str | None = None
    ) -> RackCodeCheckResponse:
        """Check whether a room rack number (slot code) is available. No serial suffixes."""
        requested = (code or preferred_base or "").strip()
        if not requested:
            return RackCodeCheckResponse(
                code="",
                available=False,
                suggestion="",
                conflict=None,
            )

        if room_id is None:
            existing = await self.repo.get_by_code(requested)
            return RackCodeCheckResponse(
                code=requested,
                available=existing is None,
                suggestion=requested,
                conflict=_conflict_info(existing) if existing else None,
            )

        existing = await self.repo.get_by_code_in_room(room_id, requested, active_only=True)
        if existing is None:
            return RackCodeCheckResponse(
                code=requested,
                available=True,
                suggestion=requested,
                conflict=None,
            )

        conflict_room = await self.room_repo.get_by_id(existing.room_id)
        return RackCodeCheckResponse(
            code=requested,
            available=False,
            suggestion=requested,
            conflict=_conflict_info(existing, conflict_room.name if conflict_room else None),
        )

    async def place_batch(
        self,
        payload: PlaceBatchRequest,
        user_id: uuid.UUID | None = None,
    ) -> PlaceBatchResult:
        mode = (payload.mode or "all").strip().lower()
        if mode not in {"all", "by_row", "by_column", "single"}:
            raise ValidationError("mode must be all | by_row | by_column | single", code=10004)

        room_id, room = await _require_active_room(self.room_repo, payload.room_id)

        row_layout = room.get_row_layout()
        codes = room.get_slot_codes()
        result = PlaceBatchResult()

        async def resolve_template(row_no: int, col_no: int) -> RackTemplate | None:
            template_id: str | None = None
            if mode == "by_row":
                template_id = payload.row_templates.get(str(row_no)) or payload.template_id
            elif mode == "by_column":
                template_id = payload.column_templates.get(str(col_no)) or payload.template_id
            else:
                template_id = payload.template_id
            if not template_id:
                return None
            return await self.template_repo.get_by_id(uuid.UUID(template_id))

        async def apply_template_to_rack(rack: Rack, template: RackTemplate) -> None:
            full = await self.repo.get_by_id_with_positions(rack.id)
            if not full:
                raise NotFoundError("Rack not found")
            if full.total_u != template.total_u:
                await self._resize_rack_positions(full, template.total_u, user_id)
                full.total_u = template.total_u
            full.width = template.width
            full.depth = template.depth
            full.rack_template_id = template.id
            full.updated_by = user_id
            full.version += 1

        # Single slot placement
        if mode == "single":
            if payload.row_no is None or payload.column_no is None:
                raise ValidationError("single mode requires row_no and column_no", code=10004)
            if not payload.template_id:
                raise ValidationError("single mode requires template_id", code=10004)
            template = await self.template_repo.get_by_id(uuid.UUID(payload.template_id))
            if not template:
                raise NotFoundError("Rack template not found")

            existing = await self.repo.get_by_position_in_room(
                room_id, payload.row_no, payload.column_no
            )
            if existing:
                if payload.update_existing:
                    try:
                        await apply_template_to_rack(existing, template)
                        slot_code = (
                            codes[payload.row_no - 1][payload.column_no - 1]
                            if payload.row_no - 1 < len(codes)
                            and payload.column_no - 1 < len(codes[payload.row_no - 1])
                            else f"R{payload.row_no:02d}{payload.column_no:02d}"
                        )
                        # Prefer room slot number; ignore client-provided serial/prefix codes.
                        identity = slot_code
                        code, name = await _slot_identity(
                            self.repo, room_id, identity, exclude_id=existing.id
                        )
                        existing.code = code
                        existing.name = name
                        result.updated += 1
                    except Exception as exc:  # noqa: BLE001
                        result.skipped += 1
                        result.errors.append(f"{existing.code}: {exc}")
                else:
                    result.skipped += 1
                    result.errors.append(f"R{payload.row_no}-C{payload.column_no}: already occupied")
            else:
                slot_code = (
                    codes[payload.row_no - 1][payload.column_no - 1]
                    if payload.row_no - 1 < len(codes)
                    and payload.column_no - 1 < len(codes[payload.row_no - 1])
                    else f"R{payload.row_no:02d}{payload.column_no:02d}"
                )
                code, name = await _slot_identity(self.repo, room_id, slot_code)
                entity = Rack(
                    room_id=room_id,
                    rack_template_id=template.id,
                    code=code,
                    name=name,
                    row_no=payload.row_no,
                    column_no=payload.column_no,
                    total_u=template.total_u,
                    width=template.width,
                    depth=template.depth,
                    status="active",
                    created_by=user_id,
                    updated_by=user_id,
                )
                created = await self.repo.create(entity)
                await _init_rack_positions(self.session, created, user_id)
                result.created += 1
            await self.session.flush()
            return result

        # Bulk: all / by_row / by_column
        if mode == "all" and not payload.template_id:
            raise ValidationError("all mode requires template_id", code=10004)
        if mode == "by_row" and not payload.row_templates and not payload.template_id:
            raise ValidationError("by_row mode requires row_templates or template_id", code=10004)
        if mode == "by_column" and not payload.column_templates and not payload.template_id:
            raise ValidationError(
                "by_column mode requires column_templates or template_id", code=10004
            )

        existing_map = {
            (r.row_no, r.column_no): r for r in await self.repo.list_by_room(room_id)
        }

        for row_idx, cols in enumerate(row_layout):
            row_no = row_idx + 1
            for col_no in range(1, cols + 1):
                template = await resolve_template(row_no, col_no)
                if not template:
                    result.skipped += 1
                    result.errors.append(f"R{row_no}-C{col_no}: 未指定模板")
                    continue

                existing = existing_map.get((row_no, col_no))
                slot_code = (
                    codes[row_idx][col_no - 1]
                    if row_idx < len(codes) and col_no - 1 < len(codes[row_idx])
                    else f"R{row_no:02d}{col_no:02d}"
                )
                if existing:
                    if not payload.update_existing:
                        continue
                    try:
                        await apply_template_to_rack(existing, template)
                        code, name = await _slot_identity(
                            self.repo, room_id, slot_code, exclude_id=existing.id
                        )
                        existing.code = code
                        existing.name = name
                        result.updated += 1
                    except Exception as exc:  # noqa: BLE001
                        result.skipped += 1
                        result.errors.append(f"{existing.code}: {exc}")
                    continue

                if not payload.fill_empty_slots:
                    continue

                try:
                    code, name = await _slot_identity(self.repo, room_id, slot_code)
                except ConflictError as exc:
                    result.skipped += 1
                    result.errors.append(f"R{row_no}-C{col_no}: {exc.message}")
                    continue
                entity = Rack(
                    room_id=room_id,
                    rack_template_id=template.id,
                    code=code,
                    name=name,
                    row_no=row_no,
                    column_no=col_no,
                    total_u=template.total_u,
                    width=template.width,
                    depth=template.depth,
                    status="active",
                    created_by=user_id,
                    updated_by=user_id,
                )
                created = await self.repo.create(entity)
                await _init_rack_positions(self.session, created, user_id)
                result.created += 1
                existing_map[(row_no, col_no)] = created

        await self.session.flush()
        return result

    async def get_layout(self, entity_id: uuid.UUID) -> RackLayoutResponse:
        rack = await self.repo.get_by_id_with_positions(entity_id)
        if not rack:
            raise NotFoundError("Rack not found", code=10001)

        devices = await self.device_repo.list_by_rack(entity_id)
        layout_devices: list[RackLayoutDevice] = []
        total_power = 0.0

        for device in devices:
            if device.u_position is None:
                continue
            power = float(device.power) if device.power is not None else None
            if power is not None:
                total_power += power
            model_name = device.model.name if device.model else None
            system_ip, bmc_ip, vip = _extract_ip_fields(device)
            layout_devices.append(
                RackLayoutDevice(
                    device_id=str(device.id),
                    hostname=device.hostname,
                    height_u=device.height_u,
                    start_u=device.u_position,
                    power=power,
                    ip_summary=system_ip,
                    bmc_ip=bmc_ip,
                    vip=vip,
                    model_name=model_name,
                )
            )

        pos_map = {p.u_position: p for p in rack.positions}
        device_by_u: dict[int, RackLayoutDevice] = {}
        for item in layout_devices:
            for offset in range(item.height_u):
                device_by_u[item.start_u + offset] = item

        # Top-down slots; device content shown once at the top U of its span.
        slots: list[RackLayoutSlot] = []
        for u in range(rack.total_u, 0, -1):
            pos = pos_map.get(u)
            device = device_by_u.get(u)
            if device:
                top_u = device.start_u + device.height_u - 1
                slots.append(
                    RackLayoutSlot(
                        u_position=u,
                        occupied=True,
                        is_span_start=(u == top_u),
                        span_height=device.height_u if u == top_u else 1,
                        device=device,
                    )
                )
            else:
                slots.append(
                    RackLayoutSlot(
                        u_position=u,
                        occupied=bool(pos and pos.occupied),
                        is_span_start=False,
                        span_height=1,
                        device=None,
                    )
                )

        return RackLayoutResponse(
            rack=_to_rack_response(rack),
            positions=[_to_position_response(pos) for pos in rack.positions],
            slots=slots,
            devices=layout_devices,
            total_power=round(total_power, 2),
        )

    async def create(
        self, payload: RackCreate, user_id: uuid.UUID | None = None
    ) -> RackResponse:
        room_id, room = await _require_active_room(self.room_repo, payload.room_id)

        existing_racks = await self.repo.list_by_room(room_id)
        row_no, column_no = _resolve_rack_position(
            room, existing_racks, payload.row_no, payload.column_no
        )
        codes = room.get_slot_codes()
        slot_code = (
            codes[row_no - 1][column_no - 1]
            if row_no - 1 < len(codes) and column_no - 1 < len(codes[row_no - 1])
            else (payload.code or payload.name or f"R{row_no:02d}{column_no:02d}")
        )
        code, name = await _slot_identity(self.repo, room_id, slot_code)

        total_u = payload.total_u
        width = payload.width
        depth = payload.depth
        template_id: uuid.UUID | None = None

        if payload.rack_template_id:
            template_id = uuid.UUID(payload.rack_template_id)
            template = await self.template_repo.get_by_id(template_id)
            if not template:
                raise NotFoundError("Rack template not found")
            total_u = template.total_u
            width = template.width
            depth = template.depth

        entity = Rack(
            room_id=room_id,
            rack_template_id=template_id,
            code=code,
            name=name,
            row_no=row_no,
            column_no=column_no,
            total_u=total_u,
            width=width,
            depth=depth,
            status=payload.status.value,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.repo.create(entity)
        await _init_rack_positions(self.session, created, user_id)
        rack = await self.repo.get_by_id_with_positions(created.id)
        assert rack is not None
        return _to_rack_response(rack)

    async def update(
        self,
        entity_id: uuid.UUID,
        payload: RackUpdate,
        user_id: uuid.UUID | None = None,
    ) -> RackResponse:
        rack = await self.repo.get_by_id_with_positions(entity_id)
        if not rack:
            raise NotFoundError("Rack not found", code=10001)

        if payload.name and payload.name != rack.name:
            existing = await self.repo.get_by_name_in_room(rack.room_id, payload.name)
            if existing:
                raise ConflictError("Rack name already exists in this room")
            rack.name = payload.name

        if payload.row_no is not None or payload.column_no is not None:
            room = await self.room_repo.get_by_id(rack.room_id)
            if not room:
                raise NotFoundError("Room not found")
            new_row = payload.row_no if payload.row_no is not None else rack.row_no
            new_col = payload.column_no if payload.column_no is not None else rack.column_no
            row_layout = room.get_row_layout()
            if (
                new_row < 1
                or new_row > len(row_layout)
                or new_col < 1
                or new_col > row_layout[new_row - 1]
            ):
                raise ValidationError(
                    f"Position exceeds room layout (row {new_row} capacity)",
                    code=10004,
                )
            if new_row != rack.row_no or new_col != rack.column_no:
                existing = await self.repo.get_by_position_in_room(rack.room_id, new_row, new_col)
                if existing and existing.id != rack.id:
                    raise ConflictError("Rack position already occupied", code=10002)
                rack.row_no = new_row
                rack.column_no = new_col
        if payload.width is not None:
            rack.width = payload.width
        if payload.depth is not None:
            rack.depth = payload.depth
        if payload.status is not None:
            rack.status = payload.status.value
        if payload.description is not None:
            rack.description = payload.description

        if payload.total_u is not None and payload.total_u != rack.total_u:
            await self._resize_rack_positions(rack, payload.total_u, user_id)
            rack.total_u = payload.total_u

        rack.updated_by = user_id
        rack.version += 1
        await self.session.flush()
        updated = await self.repo.get_by_id_with_positions(entity_id)
        assert updated is not None
        return _to_rack_response(updated)

    async def _resize_rack_positions(
        self,
        rack: Rack,
        new_total_u: int,
        user_id: uuid.UUID | None,
    ) -> None:
        if new_total_u < rack.total_u:
            positions_to_remove = [p for p in rack.positions if p.u_position > new_total_u]
            for pos in positions_to_remove:
                if pos.occupied:
                    raise ValidationError(
                        "Cannot reduce rack U count while upper positions are occupied",
                        code=10004,
                    )
                await self.position_repo.soft_delete(pos, deleted_by=user_id)
        elif new_total_u > rack.total_u:
            existing = {p.u_position for p in rack.positions}
            for u in range(rack.total_u + 1, new_total_u + 1):
                if u not in existing:
                    self.session.add(
                        RackPosition(
                            rack_id=rack.id,
                            u_position=u,
                            occupied=False,
                            created_by=user_id,
                            updated_by=user_id,
                        )
                    )
            await self.session.flush()

    async def delete(self, entity_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        rack = await self.repo.get_by_id_with_positions(entity_id)
        if not rack:
            raise NotFoundError("Rack not found", code=10001)
        if any(pos.occupied for pos in rack.positions):
            raise ConflictError("Cannot delete rack with mounted devices")
        await self.repo.soft_delete(rack, deleted_by=user_id)

    async def batch_delete(
        self,
        payload: RackBatchDeleteRequest,
        user_id: uuid.UUID | None = None,
    ) -> RackBatchDeleteResult:
        result = RackBatchDeleteResult()
        seen: set[uuid.UUID] = set()
        for raw_id in payload.ids:
            try:
                rack_id = uuid.UUID(raw_id)
            except ValueError:
                result.skipped += 1
                result.errors.append(f"{raw_id}: 无效的机柜 ID")
                continue
            if rack_id in seen:
                continue
            seen.add(rack_id)
            rack = await self.repo.get_by_id_with_positions(rack_id)
            if not rack:
                result.skipped += 1
                result.errors.append(f"{raw_id}: 机柜不存在")
                continue
            if any(pos.occupied for pos in rack.positions):
                result.skipped += 1
                result.errors.append(f"{rack.code}: 有设备占用，无法删除")
                continue
            await self.repo.soft_delete(rack, deleted_by=user_id)
            result.deleted += 1
        await self.session.flush()
        return result
