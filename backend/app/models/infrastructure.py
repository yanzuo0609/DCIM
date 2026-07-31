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
    __table_args__ = (UniqueConstraint("floor_id", "name", name="uk_room_floor_name"),)

    floor_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("floor.id"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    rack_rows: Mapped[int] = mapped_column(Integer, default=4, nullable=False)
    rack_columns: Mapped[int] = mapped_column(Integer, default=6, nullable=False)
    # Per-row rack counts, e.g. [6, 6, 8, 4]. Empty/null means uniform grid.
    row_layout: Mapped[list | None] = mapped_column(JSON, nullable=True)
    # auto | custom
    code_mode: Mapped[str] = mapped_column(String(20), default="auto", nullable=False)
    code_prefix: Mapped[str | None] = mapped_column(String(50), nullable=True)
    # Per-slot codes matching row_layout, e.g. [["A01","A02"],["B01","B02"]]
    slot_codes: Mapped[list | None] = mapped_column(JSON, nullable=True)

    floor: Mapped[Floor] = relationship(back_populates="rooms")
    # Avoid selectin: room list would otherwise hydrate every rack under each room.
    racks: Mapped[list["Rack"]] = relationship(back_populates="room", lazy="select")

    def get_row_layout(self) -> list[int]:
        if self.row_layout and isinstance(self.row_layout, list) and len(self.row_layout) > 0:
            return [int(n) for n in self.row_layout]
        return [self.rack_columns] * self.rack_rows

    def get_slot_codes(self) -> list[list[str]]:
        from app.schemas.infrastructure import generate_slot_codes

        layout = self.get_row_layout()
        if self.slot_codes and isinstance(self.slot_codes, list) and len(self.slot_codes) == len(layout):
            result: list[list[str]] = []
            valid = True
            for row_idx, cols in enumerate(layout):
                row = self.slot_codes[row_idx]
                if not isinstance(row, list) or len(row) != cols:
                    valid = False
                    break
                result.append([str(c).strip() for c in row])
            if valid:
                return result
        return generate_slot_codes(
            layout,
            code_mode="auto",
            code_prefix=self.code_prefix or "A",
            slot_codes=None,
        )

    def get_slot_code(self, row_no: int, column_no: int) -> str | None:
        codes = self.get_slot_codes()
        if row_no < 1 or row_no > len(codes):
            return None
        row = codes[row_no - 1]
        if column_no < 1 or column_no > len(row):
            return None
        return row[column_no - 1]

    @property
    def rack_capacity(self) -> int:
        return sum(self.get_row_layout())
