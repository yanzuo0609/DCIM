"""Layout Engine - U position calculation and conflict detection."""

import uuid
from dataclasses import dataclass


@dataclass
class LayoutValidation:
    valid: bool
    message: str
    occupied_positions: list[int]


def occupied_range(u_position: int, height_u: int) -> list[int]:
    return list(range(u_position, u_position + height_u))


def validate_mount(
    *,
    total_u: int,
    u_position: int,
    height_u: int,
    occupied_map: dict[int, uuid.UUID | None],
    exclude_device_id: uuid.UUID | None = None,
) -> LayoutValidation:
    if height_u < 1:
        return LayoutValidation(False, "Device height must be at least 1U", [])

    end_u = u_position + height_u - 1
    if u_position < 1 or end_u > total_u:
        return LayoutValidation(
            False,
            f"Device exceeds rack bounds (U{u_position}-U{end_u}, rack has {total_u}U)",
            [],
        )

    positions = occupied_range(u_position, height_u)
    conflicts: list[int] = []
    for u in positions:
        occupant = occupied_map.get(u)
        if occupant and occupant != exclude_device_id:
            conflicts.append(u)

    if conflicts:
        return LayoutValidation(
            False,
            f"U position conflict at U{','.join(map(str, conflicts))}",
            conflicts,
        )

    return LayoutValidation(True, "Valid layout", [])


def find_first_available(
    *,
    total_u: int,
    height_u: int,
    occupied_map: dict[int, uuid.UUID | None],
    start_u: int = 1,
    gap_u: int = 0,
) -> int | None:
    """从 start_u 起查找可用位；gap_u>0 时要求起始 U 前有 gap_u 个空闲 U（与已有设备间隔）。"""
    begin = max(1, start_u)
    for u in range(begin, total_u - height_u + 2):
        if gap_u > 0:
            blocked = False
            for g in range(1, gap_u + 1):
                prev = u - g
                if prev >= 1 and occupied_map.get(prev):
                    blocked = True
                    break
            if blocked:
                continue
        result = validate_mount(
            total_u=total_u,
            u_position=u,
            height_u=height_u,
            occupied_map=occupied_map,
        )
        if result.valid:
            return u
    return None
