from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class DataCenterCreate(BaseModel):
    code: str | None = Field(default=None, max_length=50, description="编号；空则自动生成 DCn")
    name: str = Field(min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    description: str | None = None


class DataCenterUpdate(BaseModel):
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    location: str | None = Field(default=None, max_length=200)
    description: str | None = None


class DataCenterResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    location: str | None
    description: str | None
    created_at: datetime
    updated_at: datetime


class BuildingCreate(BaseModel):
    datacenter_id: str
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class BuildingUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class BuildingResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    datacenter_id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


class FloorCreate(BaseModel):
    building_id: str
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class FloorUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class FloorResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    building_id: str
    name: str
    description: str | None
    created_at: datetime
    updated_at: datetime


def normalize_row_layout(
    *,
    layout_mode: Literal["auto", "manual"] = "auto",
    rack_rows: int | None = None,
    rack_columns: int | None = None,
    row_layout: list[int] | None = None,
) -> list[int]:
    if layout_mode == "manual":
        if not row_layout:
            raise ValueError("row_layout is required in manual mode")
        layout = [int(n) for n in row_layout]
    else:
        rows = rack_rows or 4
        cols = rack_columns or 6
        layout = [cols] * rows
    if not layout:
        raise ValueError("row_layout must not be empty")
    if any(n < 1 or n > 50 for n in layout):
        raise ValueError("each row rack count must be between 1 and 50")
    if len(layout) > 50:
        raise ValueError("row count must be between 1 and 50")
    return layout


PRESET_ROOM_ATTRIBUTES = frozenset({"internet", "private_network"})

PURPOSE_FALLBACK_LABELS: dict[str, str] = {
    "production": "生产",
    "test": "测试",
    "backup": "备份",
    "network": "网络",
    "storage": "存储",
    "other": "其他",
}


def normalize_room_attributes(raw: list[str] | None) -> list[str]:
    if not raw:
        return []
    seen: set[str] = set()
    result: list[str] = []
    for item in raw:
        value = str(item or "").strip()
        if not value:
            continue
        key = value if value in PRESET_ROOM_ATTRIBUTES else value
        lower = key.lower() if key in PRESET_ROOM_ATTRIBUTES else key
        # presets keep canonical codes; customs keep trimmed text
        if key in PRESET_ROOM_ATTRIBUTES:
            if key in seen:
                continue
            seen.add(key)
            result.append(key)
        else:
            if lower in seen or key in PRESET_ROOM_ATTRIBUTES:
                continue
            seen.add(lower)
            if len(key) > 40:
                raise ValueError("custom attribute length must be <= 40")
            result.append(key)
        if len(result) > 20:
            raise ValueError("at most 20 room attributes")
    return result


def resolve_room_attributes(
    attributes: list[str] | None,
    *,
    purpose: str | None = None,
) -> list[str]:
    normalized = normalize_room_attributes(attributes)
    if normalized:
        return normalized
    label = PURPOSE_FALLBACK_LABELS.get((purpose or "").strip())
    return [label] if label else []


def purpose_from_attributes(attributes: list[str] | None) -> str:
    """属性为主；purpose 列兼容写 other。"""
    _ = attributes
    return "other"


def ensure_layout_within_outline(
    row_layout: list[int],
    *,
    outline_rows: int,
    outline_cols: int,
) -> None:
    if outline_rows < 1 or outline_rows > 50 or outline_cols < 1 or outline_cols > 50:
        raise ValueError("outline grid must be between 1 and 50")
    if len(row_layout) > outline_rows:
        raise ValueError(
            f"机柜排数 {len(row_layout)} 超出机房轮廓宽向网格 {outline_rows}，请缩小编排或扩大轮廓"
        )
    widest = max(row_layout) if row_layout else 0
    if widest > outline_cols:
        raise ValueError(
            f"机柜列数 {widest} 超出机房轮廓长向网格 {outline_cols}，请缩小编排或扩大轮廓"
        )


def letter_to_index(label: str) -> int:
    text = label.strip().upper()
    if not text or not all("A" <= ch <= "Z" for ch in text):
        raise ValueError(f"invalid letter label: {label}")
    value = 0
    for ch in text:
        value = value * 26 + (ord(ch) - ord("A") + 1)
    return value


def index_to_letter(index: int) -> str:
    if index < 1:
        raise ValueError("letter index must be >= 1")
    chars: list[str] = []
    n = index
    while n > 0:
        n, rem = divmod(n - 1, 26)
        chars.append(chr(ord("A") + rem))
    return "".join(reversed(chars))


def expand_row_prefixes(expression: str, row_count: int) -> list[str]:
    """
    Expand rack-row letter prefixes.

    - Single letter/token ``A``: generate A, B, C... for ``row_count`` rows
    - Range ``A-D`` / ``A-BZ``: Excel-style inclusive letter range; count must cover rows
    """
    if row_count < 1:
        raise ValueError("row_count must be >= 1")
    raw = (expression or "A").strip().upper().replace(" ", "")
    if not raw:
        raw = "A"

    if "-" in raw:
        start_raw, end_raw = raw.split("-", 1)
        if not start_raw or not end_raw:
            raise ValueError("prefix range must look like A-D or A-BZ")
        start = letter_to_index(start_raw)
        end = letter_to_index(end_raw)
        if end < start:
            raise ValueError("prefix range end must be >= start")
        labels = [index_to_letter(i) for i in range(start, end + 1)]
        if len(labels) < row_count:
            raise ValueError(
                f"prefix range {raw} only has {len(labels)} letters, but room has {row_count} rows"
            )
        return labels[:row_count]

    # Single starting label: expand consecutive letters for each row
    start = letter_to_index(raw)
    return [index_to_letter(start + i) for i in range(row_count)]


def generate_slot_codes(
    row_layout: list[int],
    *,
    code_mode: Literal["auto", "custom"] = "auto",
    code_prefix: str | None = None,
    slot_codes: list[list[str]] | None = None,
) -> list[list[str]]:
    if code_mode == "custom" and slot_codes is not None:
        if len(slot_codes) != len(row_layout):
            raise ValueError("slot_codes rows must match row_layout")
        result: list[list[str]] = []
        seen: set[str] = set()
        for row_idx, cols in enumerate(row_layout):
            raw_row = slot_codes[row_idx] if row_idx < len(slot_codes) else []
            if not isinstance(raw_row, list):
                raise ValueError(f"row {row_idx + 1} must be a list of rack codes")
            # 允许短行补空：场景网格中立柱/空位可不占号
            row = [str(x) if x is not None else "" for x in raw_row[:cols]]
            if len(row) < cols:
                row.extend([""] * (cols - len(row)))
            codes: list[str] = []
            for col_idx, raw in enumerate(row):
                code = str(raw).strip()
                if not code:
                    # 空码合法（非机柜格占位），不参与唯一性校验
                    codes.append("")
                    continue
                if len(code) > 50:
                    raise ValueError(f"rack code too long: {code}")
                key = code.lower()
                if key in seen:
                    raise ValueError(f"duplicate rack code: {code}")
                seen.add(key)
                codes.append(code)
            result.append(codes)
        return result

    row_prefixes = expand_row_prefixes(code_prefix or "A", len(row_layout))
    generated: list[list[str]] = []
    seen_auto: set[str] = set()
    for row_idx, cols in enumerate(row_layout):
        prefix = row_prefixes[row_idx]
        width = max(2, len(str(cols)))
        row_codes: list[str] = []
        for col in range(1, cols + 1):
            code = f"{prefix}{col:0{width}d}"
            if code.lower() in seen_auto:
                raise ValueError(f"duplicate rack code: {code}")
            seen_auto.add(code.lower())
            row_codes.append(code)
        generated.append(row_codes)
    return generated


class RoomCreate(BaseModel):
    floor_id: str
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None
    purpose: Literal["production", "test", "backup", "network", "storage", "other"] | None = (
        "production"
    )
    importance: Literal["critical", "high", "medium", "low"] | None = "medium"
    attributes: list[str] | None = None
    outline_rows: int = Field(default=8, ge=1, le=50, description="机房轮廓宽向网格数")
    outline_cols: int = Field(default=10, ge=1, le=50, description="机房轮廓长向网格数")
    layout_mode: Literal["auto", "manual"] = "auto"
    rack_rows: int = Field(default=4, ge=1, le=50, description="机柜排数（自动模式）")
    rack_columns: int = Field(default=6, ge=1, le=50, description="每排机柜数（自动模式）")
    row_layout: list[int] | None = Field(default=None, description="每排机柜数列表（手动模式）")
    code_mode: Literal["auto", "custom"] = "auto"
    code_prefix: str | None = Field(default="A", max_length=50)
    slot_codes: list[list[str]] | None = None
    pillar_layout: dict | None = None

    @model_validator(mode="after")
    def validate_layout(self) -> "RoomCreate":
        self.attributes = normalize_room_attributes(self.attributes)
        self.row_layout = normalize_row_layout(
            layout_mode=self.layout_mode,
            rack_rows=self.rack_rows,
            rack_columns=self.rack_columns,
            row_layout=self.row_layout,
        )
        self.rack_rows = len(self.row_layout)
        self.rack_columns = max(self.row_layout)
        ensure_layout_within_outline(
            self.row_layout,
            outline_rows=self.outline_rows,
            outline_cols=self.outline_cols,
        )
        self.slot_codes = generate_slot_codes(
            self.row_layout,
            code_mode=self.code_mode,
            code_prefix=self.code_prefix,
            slot_codes=self.slot_codes,
        )
        if self.attributes:
            self.purpose = purpose_from_attributes(self.attributes)  # type: ignore[assignment]
        return self


class RoomQuickCreate(BaseModel):
    datacenter_id: str = Field(description="关联数据中心 ID")
    building_no: str = Field(min_length=1, max_length=100, description="机房楼号")
    room_no: str = Field(min_length=1, max_length=100, description="机房门牌号")
    code: str | None = Field(default=None, max_length=50, description="机房唯一编号；空则自动生成")
    description: str | None = None
    purpose: Literal["production", "test", "backup", "network", "storage", "other"] | None = (
        "other"
    )
    importance: Literal["critical", "high", "medium", "low"] | None = "medium"
    attributes: list[str] | None = None
    outline_rows: int = Field(default=8, ge=1, le=50, description="机房轮廓宽向网格数")
    outline_cols: int = Field(default=10, ge=1, le=50, description="机房轮廓长向网格数")
    layout_mode: Literal["auto", "manual"] = "auto"
    rack_rows: int = Field(default=4, ge=1, le=50, description="机柜排数（自动模式）")
    rack_columns: int = Field(default=6, ge=1, le=50, description="每排机柜数（自动模式）")
    row_layout: list[int] | None = Field(default=None, description="每排机柜数列表（手动模式）")
    code_mode: Literal["auto", "custom"] = "auto"
    code_prefix: str | None = Field(default="A", max_length=50)
    slot_codes: list[list[str]] | None = None
    pillar_layout: dict | None = None

    @model_validator(mode="after")
    def validate_layout(self) -> "RoomQuickCreate":
        self.attributes = normalize_room_attributes(self.attributes)
        self.row_layout = normalize_row_layout(
            layout_mode=self.layout_mode,
            rack_rows=self.rack_rows,
            rack_columns=self.rack_columns,
            row_layout=self.row_layout,
        )
        self.rack_rows = len(self.row_layout)
        self.rack_columns = max(self.row_layout)
        ensure_layout_within_outline(
            self.row_layout,
            outline_rows=self.outline_rows,
            outline_cols=self.outline_cols,
        )
        self.slot_codes = generate_slot_codes(
            self.row_layout,
            code_mode=self.code_mode,
            code_prefix=self.code_prefix,
            slot_codes=self.slot_codes,
        )
        if self.attributes is not None:
            self.purpose = purpose_from_attributes(self.attributes)  # type: ignore[assignment]
        return self


class RoomUpdate(BaseModel):
    room_no: str | None = Field(default=None, min_length=1, max_length=100)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    code: str | None = Field(default=None, min_length=1, max_length=50, description="机房唯一编号")
    description: str | None = None
    purpose: Literal["production", "test", "backup", "network", "storage", "other"] | None = None
    importance: Literal["critical", "high", "medium", "low"] | None = None
    attributes: list[str] | None = None
    outline_rows: int | None = Field(default=None, ge=1, le=50)
    outline_cols: int | None = Field(default=None, ge=1, le=50)
    layout_mode: Literal["auto", "manual"] | None = None
    rack_rows: int | None = Field(default=None, ge=1, le=50)
    rack_columns: int | None = Field(default=None, ge=1, le=50)
    row_layout: list[int] | None = None
    code_mode: Literal["auto", "custom"] | None = None
    code_prefix: str | None = Field(default=None, max_length=50)
    slot_codes: list[list[str]] | None = None
    pillar_layout: dict | None = None


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    floor_id: str
    name: str
    code: str = ""
    datacenter_id: str | None = None
    datacenter_name: str | None = None
    location: str | None = None
    building_no: str | None = None
    room_no: str | None = None
    layout_mode: str = "auto"
    rack_rows: int = 4
    rack_columns: int = 6
    row_layout: list[int] = Field(default_factory=lambda: [6, 6, 6, 6])
    outline_rows: int = 8
    outline_cols: int = 10
    rack_capacity: int = 24
    code_mode: str = "auto"
    code_prefix: str | None = "A"
    slot_codes: list[list[str]] = Field(default_factory=list)
    pillar_layout: dict | None = None
    purpose: str | None = "production"
    importance: str | None = "medium"
    attributes: list[str] = Field(default_factory=list)
    # 独立统计：已建机柜 / 使用中机柜 / 空余机柜(=已建−使用) / 设备数 / 容量(Σ模板U位) / 总功耗(W)
    rack_count: int = 0
    used_count: int = 0
    free_count: int = 0
    device_count: int = 0
    total_u: int = 0
    total_power: float = 0.0
    description: str | None
    created_at: datetime
    updated_at: datetime


class WarehouseCreate(BaseModel):
    room_id: str
    code: str | None = Field(default=None, max_length=50, description="编号；空则自动生成 WHn")
    name: str = Field(min_length=1, max_length=100)
    description: str | None = None


class WarehouseUpdate(BaseModel):
    room_id: str | None = None
    code: str | None = Field(default=None, min_length=1, max_length=50)
    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = None


class WarehouseResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str
    room_id: str
    room_name: str | None = None
    room_no: str | None = None
    building_no: str | None = None
    datacenter_id: str | None = None
    datacenter_name: str | None = None
    description: str | None = None
    asset_ledger_ready: bool = True
    asset_count: int = 0
    created_at: datetime
    updated_at: datetime


WAREHOUSE_ASSET_CATEGORIES = ("complete", "accessory", "material", "tool", "other")
WAREHOUSE_ASSET_STATUSES = ("new", "replace", "fault", "scrap")
WAREHOUSE_OUTBOUND_MODES = ("undetermined", "fixed")
WAREHOUSE_ASSET_UNITS = ("piece", "unit", "box", "set", "other")


class WarehouseAssetCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    quantity: int = Field(default=1, ge=1, le=999999)
    unit: str = Field(default="piece", max_length=20)
    project: str | None = Field(default=None, max_length=200)
    application: str | None = Field(default=None, max_length=200)
    category: str = Field(default="other", max_length=30)
    status: str = Field(default="new", max_length=30)
    inbound_at: datetime | None = None
    outbound_mode: str = Field(default="undetermined", max_length=20)
    outbound_at: datetime | None = None
    owner_name: str | None = Field(default=None, max_length=100)
    owner_contact: str | None = Field(default=None, max_length=100)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_enums(self) -> "WarehouseAssetCreate":
        if self.unit not in WAREHOUSE_ASSET_UNITS:
            raise ValueError("无效的数量单位")
        if self.category not in WAREHOUSE_ASSET_CATEGORIES:
            raise ValueError("无效的资产分类")
        if self.status not in WAREHOUSE_ASSET_STATUSES:
            raise ValueError("无效的资产状态")
        if self.outbound_mode not in WAREHOUSE_OUTBOUND_MODES:
            raise ValueError("无效的出库时间模式")
        if self.outbound_mode == "undetermined":
            self.outbound_at = None
        return self


class WarehouseAssetUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    quantity: int | None = Field(default=None, ge=1, le=999999)
    unit: str | None = Field(default=None, max_length=20)
    project: str | None = Field(default=None, max_length=200)
    application: str | None = Field(default=None, max_length=200)
    category: str | None = Field(default=None, max_length=30)
    status: str | None = Field(default=None, max_length=30)
    inbound_at: datetime | None = None
    outbound_mode: str | None = Field(default=None, max_length=20)
    outbound_at: datetime | None = None
    owner_name: str | None = Field(default=None, max_length=100)
    owner_contact: str | None = Field(default=None, max_length=100)
    remark: str | None = None

    @model_validator(mode="after")
    def validate_enums(self) -> "WarehouseAssetUpdate":
        if self.unit is not None and self.unit not in WAREHOUSE_ASSET_UNITS:
            raise ValueError("无效的数量单位")
        if self.category is not None and self.category not in WAREHOUSE_ASSET_CATEGORIES:
            raise ValueError("无效的资产分类")
        if self.status is not None and self.status not in WAREHOUSE_ASSET_STATUSES:
            raise ValueError("无效的资产状态")
        if self.outbound_mode is not None and self.outbound_mode not in WAREHOUSE_OUTBOUND_MODES:
            raise ValueError("无效的出库时间模式")
        if self.outbound_mode == "undetermined":
            self.outbound_at = None
        return self


class WarehouseAssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    warehouse_id: str
    name: str
    quantity: int = 1
    unit: str = "piece"
    project: str | None = None
    application: str | None = None
    category: str
    status: str
    inbound_at: datetime | None = None
    outbound_mode: str = "undetermined"
    outbound_at: datetime | None = None
    owner_name: str | None = None
    owner_contact: str | None = None
    remark: str | None = None
    created_at: datetime
    updated_at: datetime
