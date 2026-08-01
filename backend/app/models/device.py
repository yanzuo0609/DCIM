from __future__ import annotations

import enum
import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from datetime import date

from sqlalchemy import Boolean, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import BaseModel

if TYPE_CHECKING:
    from app.models.ip_address import IpAddress


class DeviceStatus(str, enum.Enum):
    STOCK = "stock"
    MOUNTED = "mounted"
    MAINTENANCE = "maintenance"
    RETIRED = "retired"


class Manufacturer(BaseModel):
    __tablename__ = "manufacturer"
    __table_args__ = (UniqueConstraint("code", name="uk_manufacturer_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    models: Mapped[list["DeviceModel"]] = relationship(back_populates="manufacturer", lazy="selectin")


class DeviceCategory(BaseModel):
    __tablename__ = "device_category"
    __table_args__ = (UniqueConstraint("code", name="uk_device_category_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    models: Mapped[list["DeviceModel"]] = relationship(back_populates="category", lazy="selectin")


class DeviceType(BaseModel):
    __tablename__ = "device_type"
    __table_args__ = (UniqueConstraint("code", name="uk_device_type_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_system: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    devices: Mapped[list["Device"]] = relationship(back_populates="device_type", lazy="selectin")


class DeviceParamProfile(BaseModel):
    __tablename__ = "device_param_profile"
    __table_args__ = (UniqueConstraint("code", name="uk_device_param_profile_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    devices: Mapped[list["Device"]] = relationship(back_populates="param_profile", lazy="selectin")


class DeviceSystemProfile(BaseModel):
    __tablename__ = "device_system_profile"
    __table_args__ = (UniqueConstraint("code", name="uk_device_system_profile_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    devices: Mapped[list["Device"]] = relationship(back_populates="system_profile", lazy="selectin")


class DeviceBmcProfile(BaseModel):
    """BMC 用户档案，可与系统用户档案分别挂接到设备。"""

    __tablename__ = "device_bmc_profile"
    __table_args__ = (UniqueConstraint("code", name="uk_device_bmc_profile_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    payload: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    devices: Mapped[list["Device"]] = relationship(back_populates="bmc_profile", lazy="selectin")


class DeviceModel(BaseModel):
    __tablename__ = "device_model"
    __table_args__ = (UniqueConstraint("code", name="uk_device_model_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("manufacturer.id"), nullable=False, index=True
    )
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_category.id"), nullable=True, index=True
    )
    height_u: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    power: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    depth: Mapped[int | None] = mapped_column(Integer, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 网络设备定义同步的面板布局；按 apply_device_name 一对多应用到设备清单
    port_layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    apply_device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    network_kind: Mapped[str | None] = mapped_column(String(20), nullable=True)

    manufacturer: Mapped[Manufacturer] = relationship(back_populates="models")
    category: Mapped[DeviceCategory | None] = relationship(back_populates="models")
    devices: Mapped[list["Device"]] = relationship(back_populates="model", lazy="selectin")
    contracts: Mapped[list["DeviceContract"]] = relationship(
        back_populates="device_model", lazy="select"
    )


class DeviceContract(BaseModel):
    """采购合同信息：设备名称/型号等手工填写，并可关联设备管理中的设备。"""

    __tablename__ = "device_contract"
    __table_args__ = (UniqueConstraint("contract_no", name="uk_device_contract_no"),)

    contract_no: Mapped[str] = mapped_column(String(100), nullable=False)
    project_no: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 完整设备明细 JSON；平行数组/拼接字段供检索与兼容
    device_items: Mapped[list | None] = mapped_column(JSON, nullable=True)
    device_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    device_model_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    manufacturer_names: Mapped[list | None] = mapped_column(JSON, nullable=True)
    device_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    device_model_name: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    manufacturer_name: Mapped[str | None] = mapped_column(String(500), nullable=True)
    # 可选关联档案型号；合同主数据以手工填写字段为准
    device_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_model.id"), nullable=True, index=True
    )
    # quantity=明细数量合计；unit_price 仅兼容旧数据；contract_total=合同总价
    quantity: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    unit_price: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    contract_total: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    # yuan=元, wan=万元
    price_unit: Mapped[str] = mapped_column(String(10), default="wan", nullable=False)
    purchase_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    device_model: Mapped[DeviceModel | None] = relationship(back_populates="contracts")
    devices: Mapped[list["Device"]] = relationship(back_populates="contract", lazy="select")


class Device(BaseModel):
    __tablename__ = "device"
    __table_args__ = (
        UniqueConstraint("serial_number", name="uk_device_serial_number"),
        UniqueConstraint("hostname", name="uk_device_hostname"),
    )

    name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    hostname: Mapped[str] = mapped_column(String(100), nullable=False)
    serial_number: Mapped[str] = mapped_column(String(100), nullable=False)
    device_model_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_model.id"), nullable=False, index=True
    )
    device_type_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_type.id"), nullable=True, index=True
    )
    param_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_param_profile.id"), nullable=True, index=True
    )
    system_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_system_profile.id"), nullable=True, index=True
    )
    bmc_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_bmc_profile.id"), nullable=True, index=True
    )
    contract_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_contract.id"), nullable=True, index=True
    )
    rack_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("rack.id"), nullable=True, index=True
    )
    u_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    height_u: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    weight: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    power: Mapped[Decimal | None] = mapped_column(Numeric(10, 2), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default=DeviceStatus.STOCK.value, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 是否已绑定网络设备定义面板；已绑定仅允许修改面板，不可重复应用
    network_panel_bound: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    model: Mapped[DeviceModel] = relationship(back_populates="devices")
    device_type: Mapped[DeviceType | None] = relationship(back_populates="devices")
    param_profile: Mapped[DeviceParamProfile | None] = relationship(back_populates="devices")
    system_profile: Mapped[DeviceSystemProfile | None] = relationship(back_populates="devices")
    bmc_profile: Mapped[DeviceBmcProfile | None] = relationship(back_populates="devices")
    contract: Mapped[DeviceContract | None] = relationship(back_populates="devices")
    ip_addresses: Mapped[list[IpAddress]] = relationship(
        "IpAddress", back_populates="device", lazy="selectin"
    )
