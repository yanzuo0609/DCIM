"""机房网格：有效机柜位（跳过立柱/空码占位）。"""

from __future__ import annotations

from typing import Any


def _pillar_cells(pillar_layout: dict | None) -> dict[str, list]:
    if not pillar_layout or not isinstance(pillar_layout.get("cells"), dict):
        return {}
    return pillar_layout["cells"]


def cell_kind(
    pillar_layout: dict | None,
    row_no: int,
    col_no: int,
) -> str | None:
    cells = _pillar_cells(pillar_layout)
    kinds = cells.get(str(row_no))
    if not isinstance(kinds, list) or col_no < 1 or col_no - 1 >= len(kinds):
        return None
    kind = kinds[col_no - 1]
    return str(kind) if kind is not None else None


def is_rack_slot(
    *,
    row_no: int,
    col_no: int,
    code: str = "",
    pillar_layout: dict | None = None,
    code_mode: str | None = None,
) -> bool:
    """是否可作为机柜位（非立柱；自定义空码视为占位空洞）。"""
    kind = cell_kind(pillar_layout, row_no, col_no)
    if kind in ("pillar", "pillar_round"):
        return False
    if kind is not None and kind not in ("rack", "empty"):
        return False
    code = (code or "").strip()
    if kind is None and (code_mode or "").lower() == "custom" and not code:
        return False
    if isinstance(_pillar_cells(pillar_layout).get(str(row_no)), list) and kind is None and not code:
        return False
    return True


def iter_rack_slots(
    row_layout: list[int],
    slot_codes: list[list[str]] | None = None,
    pillar_layout: dict | None = None,
    *,
    code_mode: str | None = None,
) -> list[tuple[int, int, str]]:
    """返回有效机柜位 (row_no, col_no, code)。"""
    slots: list[tuple[int, int, str]] = []
    for row_idx, capacity in enumerate(row_layout):
        row_no = row_idx + 1
        codes_row: list[str] = []
        if slot_codes and len(slot_codes) >= row_no and isinstance(slot_codes[row_no - 1], list):
            codes_row = [str(c or "").strip() for c in slot_codes[row_no - 1]]
        if len(codes_row) < capacity:
            codes_row = codes_row + [""] * (capacity - len(codes_row))
        else:
            codes_row = codes_row[:capacity]

        for col in range(1, capacity + 1):
            code = codes_row[col - 1]
            if not is_rack_slot(
                row_no=row_no,
                col_no=col,
                code=code,
                pillar_layout=pillar_layout,
                code_mode=code_mode,
            ):
                continue
            slots.append((row_no, col, code))
    return slots


def rack_slot_capacity(
    row_layout: list[int],
    slot_codes: list[list[str]] | None = None,
    pillar_layout: dict | None = None,
    *,
    code_mode: str | None = None,
) -> int:
    return len(iter_rack_slots(row_layout, slot_codes, pillar_layout, code_mode=code_mode))


def normalize_stored_slot_codes(
    row_layout: list[int],
    raw_codes: Any,
    *,
    code_mode: str,
    code_prefix: str | None,
) -> list[list[str]]:
    """读取/对齐 slot_codes；custom 模式保留空码，不回退成全自动编号。"""
    from app.schemas.infrastructure import generate_slot_codes

    if code_mode == "custom" and isinstance(raw_codes, list) and raw_codes:
        try:
            return generate_slot_codes(
                row_layout,
                code_mode="custom",
                code_prefix=code_prefix or "A",
                slot_codes=raw_codes,
            )
        except ValueError:
            pass
    if isinstance(raw_codes, list) and len(raw_codes) == len(row_layout):
        result: list[list[str]] = []
        valid = True
        for row_idx, cols in enumerate(row_layout):
            row = raw_codes[row_idx]
            if not isinstance(row, list):
                valid = False
                break
            # 允许短行补空，避免整表回退 auto 冲掉立柱空码
            padded = [str(c).strip() if c is not None else "" for c in row[:cols]]
            if len(padded) < cols:
                padded.extend([""] * (cols - len(padded)))
            result.append(padded)
        if valid:
            if code_mode == "custom" or any(not c for row in result for c in row):
                return result
            if all(len(row) == row_layout[i] for i, row in enumerate(result)):
                return result
    return generate_slot_codes(
        row_layout,
        code_mode="auto" if code_mode != "custom" else "custom",
        code_prefix=code_prefix or "A",
        slot_codes=raw_codes if code_mode == "custom" and isinstance(raw_codes, list) else None,
    )
