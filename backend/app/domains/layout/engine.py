"""Layout Engine - U position calculation and conflict detection."""

import uuid
from dataclasses import dataclass
from typing import Literal


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
        if u not in occupied_map:
            continue
        occupant = occupied_map[u]
        # occupied_map 含已占用 U（device_id 可为 None 的残留占用）
        if exclude_device_id is not None and occupant == exclude_device_id:
            continue
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
    gap_with_existing: bool = False,
    direction: Literal["up", "down"] = "up",
) -> int | None:
    """从 start_u 起查找可用位。

    gap_with_existing=True 且 gap_u>0 时：落在占用块上则跳过整块并再留 gap_u，
    再继续搜索。不因「下方紧邻已有设备」拒绝空闲 U（否则顶部 U44 在 U43
    有设备时会被误判不可上架）。

    direction:
    - up：U 号增大方向（自下而上补位）
    - down：U 号减小方向（自指定起始 U 向机柜下方/低 U 放置，适合顶置交换机）
    """
    max_start = total_u - height_u + 1
    if max_start < 1:
        return None
    gap = gap_u if gap_with_existing else 0

    if direction == "down":
        begin = min(max(1, start_u), max_start)
        u = begin
        while u >= 1:
            if u in occupied_map:
                # 跳到占用块下方（更低 U），并预留间隔
                low = u
                while low - 1 in occupied_map:
                    low -= 1
                u = low - 1 - gap
                continue

            result = validate_mount(
                total_u=total_u,
                u_position=u,
                height_u=height_u,
                occupied_map=occupied_map,
            )
            if result.valid:
                return u
            u -= 1
        return None

    begin = max(1, start_u)
    u = begin
    while u <= max_start:
        # 落在占用块上：跳过整块占用，并预留设备间隔
        if u in occupied_map:
            end = u
            while end + 1 in occupied_map:
                end += 1
            u = end + 1 + gap
            continue

        result = validate_mount(
            total_u=total_u,
            u_position=u,
            height_u=height_u,
            occupied_map=occupied_map,
        )
        if result.valid:
            return u
        u += 1
    return None


def pick_mount_u(
    *,
    total_u: int,
    height_u: int,
    occupied_map: dict[int, uuid.UUID | None],
    start_u: int = 1,
    gap_u: int = 0,
    prefer_exact: bool = True,
    direction: Literal["up", "down"] = "up",
) -> int | None:
    """批量上架选位。

    - prefer_exact=True：仅尝试指定 U（只校验占用与机柜边界，不因邻位设备拒装）
    - prefer_exact=False：占用则跳过整块并留出 gap_u，按 direction 继续找空闲位
    """
    begin = max(1, start_u)
    gap = max(0, int(gap_u or 0))

    if prefer_exact:
        exact = validate_mount(
            total_u=total_u,
            u_position=begin,
            height_u=height_u,
            occupied_map=occupied_map,
        )
        return begin if exact.valid else None

    return find_first_available(
        total_u=total_u,
        height_u=height_u,
        occupied_map=occupied_map,
        start_u=begin,
        gap_u=gap,
        gap_with_existing=True,
        direction=direction,
    )
