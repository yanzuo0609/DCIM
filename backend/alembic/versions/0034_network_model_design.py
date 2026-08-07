"""network model design: folders, design models, wiring rules

Revision ID: 0034_network_model_design
Revises: 0033_personnel
Create Date: 2026-08-06
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0034_network_model_design"
down_revision = "0033_personnel"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

    if not _table_exists("network_model_folder"):
        op.create_table(
            "network_model_folder",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("parent_id", sa.Uuid(as_uuid=True), sa.ForeignKey("network_model_folder.id"), nullable=True),
            sa.Column("kind", sa.String(20), nullable=False, server_default="folder"),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("code", sa.String(80), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_network_model_folder_parent_id", "network_model_folder", ["parent_id"])

    if not _table_exists("network_design_model"):
        op.create_table(
            "network_design_model",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "folder_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("network_model_folder.id"),
                nullable=False,
            ),
            sa.Column("code", sa.String(80), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("category", sa.String(40), nullable=False),
            sa.Column("subtype", sa.String(40), nullable=False),
            sa.Column("manufacturer_name", sa.String(100), nullable=True),
            sa.Column("vendor_sku", sa.String(100), nullable=True),
            sa.Column("height_u", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("attributes", json_type, nullable=True),
            sa.Column("port_layout", json_type, nullable=True),
            sa.Column(
                "device_model_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("device_model.id"),
                nullable=True,
            ),
            sa.Column("contract_device_name", sa.String(100), nullable=True),
            sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.UniqueConstraint("code", name="uk_network_design_model_code"),
        )
        op.create_index("ix_network_design_model_folder_id", "network_design_model", ["folder_id"])
        op.create_index("ix_network_design_model_device_model_id", "network_design_model", ["device_model_id"])

    if not _table_exists("network_wiring_rule"):
        op.create_table(
            "network_wiring_rule",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "topology_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("network_topology.id"),
                nullable=False,
            ),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("enabled", sa.Boolean(), nullable=False, server_default=sa.text("true")),
            sa.Column("mode", sa.String(20), nullable=False, server_default="sequential"),
            sa.Column("config", json_type, nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_network_wiring_rule_topology_id", "network_wiring_rule", ["topology_id"])


def downgrade() -> None:
    if _table_exists("network_wiring_rule"):
        op.drop_table("network_wiring_rule")
    if _table_exists("network_design_model"):
        op.drop_table("network_design_model")
    if _table_exists("network_model_folder"):
        op.drop_table("network_model_folder")
