import uuid

from sqlalchemy import Boolean, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class NetworkProject(BaseModel):
    __tablename__ = "network_project"
    __table_args__ = (UniqueConstraint("code", name="uk_network_project_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    topologies: Mapped[list["NetworkTopology"]] = relationship(
        "NetworkTopology",
        back_populates="project",
    )


class NetworkTopology(BaseModel):
    __tablename__ = "network_topology"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    project_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_project.id"),
        nullable=True,
        index=True,
    )

    project: Mapped["NetworkProject | None"] = relationship(
        "NetworkProject",
        back_populates="topologies",
    )
    nodes: Mapped[list["NetworkNode"]] = relationship(
        "NetworkNode",
        back_populates="topology",
        cascade="all, delete-orphan",
    )
    links: Mapped[list["NetworkLink"]] = relationship(
        "NetworkLink",
        back_populates="topology",
        cascade="all, delete-orphan",
    )


class NetworkNode(BaseModel):
    __tablename__ = "network_node"

    topology_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_topology.id"),
        nullable=False,
        index=True,
    )
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("device.id"),
        nullable=True,
        index=True,
    )
    # 关联合同「厂商型号采购汇总」对应的档案型号；contract_device_name 用于按设备名称一对多应用面板
    device_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("device_model.id"),
        nullable=True,
        index=True,
    )
    contract_device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    pos_x: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    pos_y: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    switch_port_count: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    slots: Mapped[list | None] = mapped_column(JSON, nullable=True)
    port_layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    on_canvas: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    topology: Mapped["NetworkTopology"] = relationship("NetworkTopology", back_populates="nodes")


class NetworkLink(BaseModel):
    __tablename__ = "network_link"

    topology_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_topology.id"),
        nullable=False,
        index=True,
    )
    link_type: Mapped[str] = mapped_column(String(30), nullable=False)
    source_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_node.id"),
        nullable=False,
        index=True,
    )
    source_port: Mapped[str] = mapped_column(String(50), nullable=False)
    target_node_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_node.id"),
        nullable=False,
        index=True,
    )
    target_port: Mapped[str] = mapped_column(String(50), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    source_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    target_label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    cable_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    interface_class: Mapped[str | None] = mapped_column(String(30), nullable=True)
    link_role: Mapped[str | None] = mapped_column(String(30), nullable=True)

    topology: Mapped["NetworkTopology"] = relationship("NetworkTopology", back_populates="links")
