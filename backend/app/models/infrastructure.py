import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.rack import Rack


class DataCenter(BaseModel):
    __tablename__ = "datacenter"
    __table_args__ = (UniqueConstraint("code", name="uk_datacenter_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    location: Mapped[str | None] = mapped_column(String(200), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    buildings: Mapped[list["Building"]] = relationship(
        back_populates="datacenter", lazy="selectin"
    )


class Building(BaseModel):
    __tablename__ = "building"
    __table_args__ = (
        UniqueConstraint("datacenter_id", "name", name="uk_building_datacenter_name"),
    )

    datacenter_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("datacenter.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    datacenter: Mapped[DataCenter] = relationship(back_populates="buildings")
    floors: Mapped[list["Floor"]] = relationship(back_populates="building", lazy="selectin")


class Floor(BaseModel):
    __tablename__ = "floor"
    __table_args__ = (UniqueConstraint("building_id", "name", name="uk_floor_building_name"),)

    building_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("building.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    building: Mapped[Building] = relationship(back_populates="floors")
    rooms: Mapped[list["Room"]] = relationship(back_populates="floor", lazy="selectin")


class Room(BaseModel):
    __tablename__ = "room"
    __table_args__ = (
        UniqueConstraint("floor_id", "name", name="uk_room_floor_name"),
        UniqueConstraint("code", name="uk_room_code"),
    )

    floor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("floor.id"), nullable=False, index=True
    )
    # 机房业务编号（全局唯一），与 UUID 主键并存，便于配置与定位
    code: Mapped[str] = mapped_column(String(50), nullable=False, default="")
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rack_rows: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    rack_columns: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    # Per-row rack counts, e.g. [6, 6, 8, 4]. Empty/null means uniform grid.
    row_layout: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 机房轮廓网格（与机柜编排分离）：宽方向排数 × 长方向列数
    outline_rows: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    outline_cols: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    # auto | custom
    code_mode: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)
    code_prefix: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Per-slot codes matching row_layout, e.g. [["A01","A02"],["B01","B02"]]
    slot_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # 3D 立柱布局：{"mode":"auto_middle"|"cells","cells":{"1":["rack","pillar",...]}}
    pillar_layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # production | test | backup | network | storage | other（兼容保留；展示以 attributes 为准）
    purpose: Mapped[str | None] = mapped_column(String(50), nullable=True, default="production")
    # critical | high | medium | low
    importance: Mapped[str | None] = mapped_column(String(20), nullable=True, default="medium")
    # 机房属性标签：["internet","private_network","自定义"]
    attributes: Mapped[list | None] = mapped_column(JSON, nullable=True)

    floor: Mapped[Floor] = relationship(back_populates="rooms")
    # Avoid selectin: room list would otherwise hydrate every rack under each room.
    racks: Mapped[list["Rack"]] = relationship(back_populates="room", lazy="select")

    def get_row_layout(self) -> list[int]:
        if self.row_layout and isinstance(self.row_layout, list) and len(self.row_layout) > 0:
            return [int(n) for n in self.row_layout]
        return [self.rack_columns] * self.rack_rows

    def get_slot_codes(self) -> list[list[str]]:
        from app.utils.room_layout import normalize_stored_slot_codes

        layout = self.get_row_layout()
        return normalize_stored_slot_codes(
            layout,
            self.slot_codes,
            code_mode=self.code_mode or "auto",
            code_prefix=self.code_prefix or "A",
        )

    def get_slot_code(self, row_no: int, column_no: int) -> str | None:
        codes = self.get_slot_codes()
        if row_no < 1 or row_no > len(codes):
            return None
        row = codes[row_no - 1]
        if column_no < 1 or column_no > len(row):
            return None
        return row[column_no - 1]

    def get_rack_slots(self) -> list[tuple[int, int, str]]:
        from app.utils.room_layout import iter_rack_slots

        return iter_rack_slots(
            self.get_row_layout(),
            self.get_slot_codes(),
            self.pillar_layout if isinstance(self.pillar_layout, dict) else None,
            code_mode=self.code_mode or "auto",
        )

    @property
    def rack_capacity(self) -> int:
        """有效机柜位数量（不含立柱占位）。"""
        from app.utils.room_layout import rack_slot_capacity

        return rack_slot_capacity(
            self.get_row_layout(),
            self.slot_codes if isinstance(self.slot_codes, list) else self.get_slot_codes(),
            self.pillar_layout if isinstance(self.pillar_layout, dict) else None,
            code_mode=self.code_mode or "auto",
        )
