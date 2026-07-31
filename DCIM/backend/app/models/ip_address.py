import enum
import uuid

from sqlalchemy import ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import BaseModel


class IpBindType(str, enum.Enum):
    NONE = "none"
    DEVICE = "device"
    RACK = "rack"
    RACK_RANGE = "rack_range"


class IpStatus(str, enum.Enum):
    """地址使用状态：空闲 / 已分配 / 已禁用 / 保留。"""

    FREE = "free"
    ALLOCATED = "allocated"
    DISABLED = "disabled"
    RESERVED = "reserved"


class IpSegment(BaseModel):
    """IP 地址段：列表一行，字段对齐业务地址段台账。"""

    __tablename__ = "ip_segment"

    # 台账字段
    application: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)  # 应用
    network: Mapped[str] = mapped_column(String(64), nullable=False, index=True)  # IP地址段 如 172.17.0.0
    prefix_len: Mapped[int] = mapped_column(Integer, nullable=False, default=24)  # 掩码 如 24
    gateway: Mapped[str | None] = mapped_column(String(64), nullable=True)
    address_purpose: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)  # 地址用途
    network_type: Mapped[str | None] = mapped_column(String(50), nullable=True)  # 网络类型
    location: Mapped[str | None] = mapped_column(String(100), nullable=True)  # 所属机房位置
    remarks: Mapped[str | None] = mapped_column(Text, nullable=True)  # 备注

    # 兼容旧字段 / 展开范围
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    start_ip: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    end_ip: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    netmask: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dns: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dns_secondary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    application_type: Mapped[str | None] = mapped_column(String(50), nullable=True, index=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    addresses: Mapped[list["IpAddress"]] = relationship(
        back_populates="segment",
        lazy="select",
    )


class IpAddress(BaseModel):
    """IP 地址记录：系统 IP / BMC IP / 虚拟 IP 保持对应关系。"""

    __tablename__ = "ip_address"
    __table_args__ = (UniqueConstraint("system_ip", name="uk_ip_address_system_ip"),)

    segment_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("ip_segment.id"), nullable=True, index=True
    )
    system_ip: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    bmc_ip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    vip: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    netmask: Mapped[str | None] = mapped_column(String(64), nullable=True)
    gateway: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dns: Mapped[str | None] = mapped_column(String(64), nullable=True)
    dns_secondary: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20),
        default=IpStatus.FREE.value,
        nullable=False,
        index=True,
        comment="free/allocated/disabled/reserved",
    )

    bind_type: Mapped[str] = mapped_column(
        String(20), default=IpBindType.NONE.value, nullable=False
    )
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device.id"), nullable=True, index=True
    )
    rack_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rack.id"), nullable=True, index=True
    )
    room_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("room.id"), nullable=True, index=True
    )
    scope_rack_ids: Mapped[list | None] = mapped_column(
        JSON, nullable=True, comment="机柜范围绑定的 rack id 列表"
    )
    u_position: Mapped[int | None] = mapped_column(Integer, nullable=True)

    segment = relationship("IpSegment", back_populates="addresses", lazy="selectin")
    device = relationship("Device", back_populates="ip_addresses", lazy="selectin")
    rack = relationship("Rack", lazy="selectin")
    room = relationship("Room", lazy="selectin")
