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
) -> int | None:
    """从 start_u 起查找可用位。

    gap_with_existing=True 且 gap_u>0 时：候选 U 前必须有 gap_u 个空闲 U
    （与已有设备间隔）。例如已有设备在 U3–4、U6–7、U9–10，间隔 1U、高度 2U
    时，从 U3 起应落到 U12。
    """
    begin = max(1, start_u)
    u = begin
    while u <= total_u - height_u + 1:
        # 落在占用块上：跳过整块占用，并预留设备间隔
        if u in occupied_map:
            end = u
            while end + 1 in occupied_map:
                end += 1
            u = end + 1 + (gap_u if gap_with_existing else 0)
            continue

        if gap_with_existing and gap_u > 0:
            blocked = False
            for g in range(1, gap_u + 1):
                prev = u - g
                if prev >= 1 and prev in occupied_map:
                    blocked = True
                    break
            if blocked:
                u += 1
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
) -> int | None:
    """批量上架选位。

    - prefer_exact=True：仅尝试指定 U（仍校验与已有设备的间隔）
    - prefer_exact=False：占用则跳过整块并留出 gap_u，向后找下一个合法空闲位
    """
    begin = max(1, start_u)
    gap = max(0, int(gap_u or 0))

    if prefer_exact:
        if gap > 0:
            for g in range(1, gap + 1):
                prev = begin - g
                if prev >= 1 and prev in occupied_map:
                    return None
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
    )
