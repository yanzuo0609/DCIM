import enum
import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class RackStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"


class RackTemplate(BaseModel):
    __tablename__ = "rack_template"
    __table_args__ = (UniqueConstraint("code", name="uk_rack_template_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    total_u: Mapped[int] = mapped_column(Integer, default=42, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    # classic | schematic | realistic | grid — 机柜立面视觉样式（classic 为原深色默认）
    visual_style: Mapped[str] = mapped_column(String(30), default="classic", nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    racks: Mapped[list["Rack"]] = relationship(back_populates="template", lazy="select")


class Rack(BaseModel):
    __tablename__ = "rack"
    __table_args__ = (
        UniqueConstraint("room_id", "code", name="uk_rack_room_code"),
        UniqueConstraint("room_id", "name", name="uk_rack_room_name"),
        UniqueConstraint("room_id", "seq_no", name="uk_rack_room_seq_no"),
    )

    room_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("room.id"), nullable=False, index=True
    )
    rack_template_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rack_template.id"), nullable=True
    )
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    # 机房内顺序编号（1-based，跳过立柱），便于划范围与定位；编排样式仍以 code/行列为准
    seq_no: Mapped[int | None] = mapped_column(Integer, nullable=True)
    row_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    column_no: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    total_u: Mapped[int] = mapped_column(Integer, default=42, nullable=False)
    width: Mapped[int] = mapped_column(Integer, default=600, nullable=False)
    depth: Mapped[int] = mapped_column(Integer, default=1000, nullable=False)
    visual_style: Mapped[str] = mapped_column(String(30), default="classic", nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=RackStatus.ACTIVE.value, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 机柜用途标签与展示色（布局图着色，提示应用部署）
    app_usage: Mapped[str | None] = mapped_column(String(100), nullable=True)
    app_color: Mapped[str | None] = mapped_column(String(20), nullable=True)

    room: Mapped["Room"] = relationship(back_populates="racks")
    template: Mapped[RackTemplate | None] = relationship(back_populates="racks")
    # Use select (not selectin) so list/catalog queries do not hydrate all U slots.
    positions: Mapped[list["RackPosition"]] = relationship(
        back_populates="rack", lazy="select", order_by="RackPosition.u_position"
    )


class RackPosition(BaseModel):
    __tablename__ = "rack_position"
    __table_args__ = (
        UniqueConstraint("rack_id", "u_position", name="uk_rack_position_u"),
    )

    rack_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rack.id"), nullable=False, index=True
    )
    u_position: Mapped[int] = mapped_column(Integer, nullable=False)
    occupied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)

    rack: Mapped[Rack] = relationship(back_populates="positions")
