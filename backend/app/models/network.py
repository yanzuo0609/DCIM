import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, Uuid
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import BaseModel


class NetworkProject(BaseModel):
    __tablename__ = "network_project"
    __table_args__ = (UniqueConstraint("code", name="uk_network_project_code"),)

    code: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    # 绑定的模型设计根目录（项目或文件夹）
    model_root_folder_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_model_folder.id"),
        nullable=True,
        index=True,
    )

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
    # 来自模型设计的模板实例
    design_model_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_design_model.id"),
        nullable=True,
        index=True,
    )
    contract_device_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    # 网络角色 CORE/AGG/ACCESS/SERVER/FIREWALL；可覆盖模型继承值
    network_role: Mapped[str | None] = mapped_column(String(20), nullable=True)
    device_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    # 多设备组：JSON 字符串数组，可与 device_group 并存（首个同步到 device_group）
    device_groups: Mapped[list | None] = mapped_column(JSON, nullable=True)
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
    connection_type: Mapped[str | None] = mapped_column(String(30), nullable=True)
    speed: Mapped[str | None] = mapped_column(String(20), nullable=True)
    lag_group: Mapped[str | None] = mapped_column(String(80), nullable=True)
    redundancy_path: Mapped[str | None] = mapped_column(String(10), nullable=True)
    media: Mapped[str | None] = mapped_column(String(30), nullable=True)
    module: Mapped[str | None] = mapped_column(String(80), nullable=True)
    cable_length_m: Mapped[float | None] = mapped_column(Float, nullable=True)
    wiring_rule_id: Mapped[uuid.UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    line_style: Mapped[str | None] = mapped_column(String(40), nullable=True)

    topology: Mapped["NetworkTopology"] = relationship("NetworkTopology", back_populates="links")


class NetworkLabSession(BaseModel):
    """拓扑与外部仿真实验室（Eve-NG / GNS3）的会话映射。"""

    __tablename__ = "network_lab_session"

    topology_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("network_topology.id"),
        nullable=False,
        unique=True,
        index=True,
    )
    # eve-ng | gns3 | none
    engine: Mapped[str] = mapped_column(String(20), nullable=False, default="eve-ng")
    external_lab_path: Mapped[str | None] = mapped_column(String(500), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="idle")
    last_sync_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    # { network_node_id: external_node_id }
    node_map: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    # { network_node_id: running|stopped|error }
    node_status: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    topology: Mapped["NetworkTopology"] = relationship("NetworkTopology")
