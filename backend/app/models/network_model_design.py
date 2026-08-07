"""Network model design: folders/projects, design models, wiring rules."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.models.base import BaseModel


class NetworkModelFolder(BaseModel):
    """文件夹或项目节点（树）。kind=folder|project。"""

    __tablename__ = "network_model_folder"

    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_model_folder.id"),
        nullable=True,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False, default="folder")
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    parent: Mapped["NetworkModelFolder | None"] = relationship(
        "NetworkModelFolder",
        remote_side="NetworkModelFolder.id",
        back_populates="children",
    )
    children: Mapped[list["NetworkModelFolder"]] = relationship(
        "NetworkModelFolder",
        back_populates="parent",
    )
    models: Mapped[list["NetworkDesignModel"]] = relationship(
        "NetworkDesignModel",
        back_populates="folder",
    )


class NetworkDesignModel(BaseModel):
    """模型设计条目：分类/子类型 + 专业属性 + 可选面板布局。"""

    __tablename__ = "network_design_model"
    __table_args__ = (UniqueConstraint("code", name="uk_network_design_model_code"),)

    folder_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_model_folder.id"),
        nullable=False,
        index=True,
    )
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    # server | network | security | software
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    # compute/storage/hpc | switch/router/... | firewall/... | cloud/...
    subtype: Mapped[str] = mapped_column(String(40), nullable=False)
    manufacturer_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    vendor_sku: Mapped[str | None] = mapped_column(String(100), nullable=True)
    height_u: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    # 分类属性 JSON（CPU/内存/Slot/上下联/授权等）
    attributes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # 可视化面板（物理设备）；软件类可为空
    port_layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    device_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("device_model.id"),
        nullable=True,
        index=True,
    )
    contract_device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    folder: Mapped["NetworkModelFolder"] = relationship(
        "NetworkModelFolder", back_populates="models"
    )


class NetworkWiringRule(BaseModel):
    """拓扑自动/半自动布线规则。"""

    __tablename__ = "network_wiring_rule"

    topology_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_topology.id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # sequential | manual
    mode: Mapped[str] = mapped_column(String(20), nullable=False, default="sequential")
    # { source: {node_ids|design_model_id, port_types?, port_ids?}, target: {...}, pairs?, max_links?, cable_type?, business_plane? }
    config: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
