import uuid

from sqlalchemy import Float, ForeignKey, Integer, String, Text, Uuid
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class NetworkTopology(BaseModel):
    __tablename__ = "network_topology"

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

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
    pos_x: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    pos_y: Mapped[float] = mapped_column(Float, nullable=False, default=100.0)
    switch_port_count: Mapped[int] = mapped_column(Integer, nullable=False, default=48)
    slots: Mapped[list | None] = mapped_column(JSON, nullable=True)
    port_layout: Mapped[dict | None] = mapped_column(JSON, nullable=True)

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

    topology: Mapped["NetworkTopology"] = relationship("NetworkTopology", back_populates="links")
