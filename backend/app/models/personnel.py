"""Personnel management: org charts, internal contacts, supplier contacts."""

from __future__ import annotations

import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import BaseModel

JsonType = JSON().with_variant(JSONB(), "postgresql")


class PersonnelOrgChart(BaseModel):
    __tablename__ = "personnel_org_chart"

    project_no: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    canvas_json: Mapped[dict | list | None] = mapped_column(JsonType, nullable=True)

    nodes: Mapped[list["PersonnelOrgNode"]] = relationship(
        back_populates="chart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    links: Mapped[list["PersonnelOrgLink"]] = relationship(
        back_populates="chart",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PersonnelOrgNode(BaseModel):
    __tablename__ = "personnel_org_node"

    chart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("personnel_org_chart.id"), nullable=False, index=True
    )
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("personnel_org_node.id"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    role_title: Mapped[str | None] = mapped_column(String(100), nullable=True)
    person_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pos_x: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    pos_y: Mapped[float] = mapped_column(Float, nullable=False, default=0)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    chart: Mapped["PersonnelOrgChart"] = relationship(back_populates="nodes")


class PersonnelOrgLink(BaseModel):
    __tablename__ = "personnel_org_link"
    __table_args__ = (
        UniqueConstraint("chart_id", "source_node_id", "target_node_id", name="uk_personnel_org_link"),
    )

    chart_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("personnel_org_chart.id"), nullable=False, index=True
    )
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("personnel_org_node.id"), nullable=False
    )
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("personnel_org_node.id"), nullable=False
    )

    chart: Mapped["PersonnelOrgChart"] = relationship(back_populates="links")


class PersonnelInternal(BaseModel):
    """用户相关方（手工维护，不关联系统登录账号）。"""

    __tablename__ = "personnel_internal"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role_title: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    company: Mapped[str | None] = mapped_column(String(200), nullable=True)
    project_no: Mapped[str | None] = mapped_column(String(100), nullable=True, index=True)
    org_node_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("personnel_org_node.id"), nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class PersonnelSupplier(BaseModel):
    """供应商相关方：同一厂商可多人。"""

    __tablename__ = "personnel_supplier"

    name: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    role_title: Mapped[str] = mapped_column(String(100), nullable=False, default="")
    phone: Mapped[str | None] = mapped_column(String(50), nullable=True)
    email: Mapped[str | None] = mapped_column(String(100), nullable=True)
    wechat: Mapped[str | None] = mapped_column(String(100), nullable=True)
    manufacturer_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("manufacturer.id"), nullable=False, index=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    contracts: Mapped[list["PersonnelSupplierContract"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    products: Mapped[list["PersonnelSupplierProduct"]] = relationship(
        back_populates="supplier",
        cascade="all, delete-orphan",
        lazy="selectin",
    )


class PersonnelSupplierContract(BaseModel):
    __tablename__ = "personnel_supplier_contract"
    __table_args__ = (
        UniqueConstraint("supplier_id", "contract_id", name="uk_personnel_supplier_contract"),
    )

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("personnel_supplier.id"), nullable=False, index=True
    )
    contract_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_contract.id"), nullable=False, index=True
    )

    supplier: Mapped["PersonnelSupplier"] = relationship(back_populates="contracts")


class PersonnelSupplierProduct(BaseModel):
    __tablename__ = "personnel_supplier_product"

    supplier_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("personnel_supplier.id"), nullable=False, index=True
    )
    device_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("device_model.id"), nullable=True
    )
    device_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    device_model_name: Mapped[str | None] = mapped_column(String(200), nullable=True)

    supplier: Mapped["PersonnelSupplier"] = relationship(back_populates="products")
