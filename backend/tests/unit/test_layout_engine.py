"""Unit tests for layout U placement helpers."""

import uuid

from app.domains.layout.engine import find_first_available, pick_mount_u, validate_mount


def _block(start: int, height: int, device_id: uuid.UUID | None = None) -> dict[int, uuid.UUID]:
    did = device_id or uuid.uuid4()
    return {u: did for u in range(start, start + height)}


def test_gap_skips_occupied_blocks_to_u12():
    """U3/U6/U9 为 2U 设备、间隔 1U 时，应从 U12 起放。"""
    occupied: dict[int, uuid.UUID | None] = {}
    occupied.update(_block(3, 2))
    occupied.update(_block(6, 2))
    occupied.update(_block(9, 2))

    u = pick_mount_u(
        total_u=49,
        height_u=2,
        occupied_map=occupied,
        start_u=3,
        gap_u=1,
        prefer_exact=False,
    )
    assert u == 12


def test_gap_from_start_u1_places_before_blocks_when_free():
    """起始 U1 且前方空闲时，仍可落在 U1（不必强行跳到 12）。"""
    occupied: dict[int, uuid.UUID | None] = {}
    occupied.update(_block(3, 2))
    occupied.update(_block(6, 2))
    occupied.update(_block(9, 2))

    u = pick_mount_u(
        total_u=49,
        height_u=2,
        occupied_map=occupied,
        start_u=1,
        gap_u=1,
        prefer_exact=False,
    )
    assert u == 1


def test_one_u_devices_with_gap():
    """1U 在 U3，间隔 1U、从 U3 起 → 跳过占用并留 1U 后落到 U5。"""
    occupied: dict[int, uuid.UUID | None] = {}
    occupied.update(_block(3, 1))
    occupied.update(_block(6, 1))
    occupied.update(_block(9, 1))

    u = pick_mount_u(
        total_u=49,
        height_u=1,
        occupied_map=occupied,
        start_u=3,
        gap_u=1,
        prefer_exact=False,
    )
    assert u == 5


def test_pick_mount_u_exact_respects_gap():
    occupied = _block(45, 1)
    u = pick_mount_u(
        total_u=49,
        height_u=1,
        occupied_map=occupied,
        start_u=46,
        gap_u=1,
        prefer_exact=True,
    )
    assert u is None


def test_find_first_available_basic():
    occupied = {1: uuid.uuid4(), 2: uuid.uuid4()}
    u = find_first_available(
        total_u=10,
        height_u=1,
        occupied_map=occupied,
        start_u=1,
        gap_u=0,
        gap_with_existing=False,
    )
    assert u == 3


def test_validate_mount_conflict_at_46():
    occupied = {46: uuid.uuid4()}
    result = validate_mount(
        total_u=49,
        u_position=46,
        height_u=1,
        occupied_map=occupied,
    )
    assert result.valid is False
