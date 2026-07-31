"""Add network design tables."""

from alembic import op
import sqlalchemy as sa


revision = "0017_network_design"
down_revision = "0016_device_contract_items_total"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "network_topology",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )

    op.create_table(
        "network_node",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("topology_id", sa.Uuid(), nullable=False),
        sa.Column("kind", sa.String(length=20), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("pos_x", sa.Float(), nullable=False, server_default="100"),
        sa.Column("pos_y", sa.Float(), nullable=False, server_default="100"),
        sa.Column("switch_port_count", sa.Integer(), nullable=False, server_default="48"),
        sa.Column("slots", sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(["topology_id"], ["network_topology.id"]),
        sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_network_node_topology_id", "network_node", ["topology_id"])
    op.create_index("ix_network_node_device_id", "network_node", ["device_id"])

    op.create_table(
        "network_link",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("topology_id", sa.Uuid(), nullable=False),
        sa.Column("link_type", sa.String(length=30), nullable=False),
        sa.Column("source_node_id", sa.Uuid(), nullable=False),
        sa.Column("source_port", sa.String(length=50), nullable=False),
        sa.Column("target_node_id", sa.Uuid(), nullable=False),
        sa.Column("target_port", sa.String(length=50), nullable=False),
        sa.Column("label", sa.String(length=200), nullable=True),
        sa.ForeignKeyConstraint(["topology_id"], ["network_topology.id"]),
        sa.ForeignKeyConstraint(["source_node_id"], ["network_node.id"]),
        sa.ForeignKeyConstraint(["target_node_id"], ["network_node.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_network_link_topology_id", "network_link", ["topology_id"])
    op.create_index("ix_network_link_source_node_id", "network_link", ["source_node_id"])
    op.create_index("ix_network_link_target_node_id", "network_link", ["target_node_id"])


def downgrade() -> None:
    op.drop_index("ix_network_link_target_node_id", table_name="network_link")
    op.drop_index("ix_network_link_source_node_id", table_name="network_link")
    op.drop_index("ix_network_link_topology_id", table_name="network_link")
    op.drop_table("network_link")
    op.drop_index("ix_network_node_device_id", table_name="network_node")
    op.drop_index("ix_network_node_topology_id", table_name="network_node")
    op.drop_table("network_node")
    op.drop_table("network_topology")
