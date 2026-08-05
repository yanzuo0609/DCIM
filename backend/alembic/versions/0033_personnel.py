"""personnel tables: org charts, internal & supplier contacts

Revision ID: 0033_personnel
Revises: 0032_device_manufacturer
Create Date: 2026-08-05
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0033_personnel"
down_revision = "0032_device_manufacturer"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

    if not _table_exists("personnel_org_chart"):
        op.create_table(
            "personnel_org_chart",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("project_no", sa.String(100), nullable=False),
            sa.Column("name", sa.String(200), nullable=False),
            sa.Column("canvas_json", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_personnel_org_chart_project_no", "personnel_org_chart", ["project_no"])

    if not _table_exists("personnel_org_node"):
        op.create_table(
            "personnel_org_node",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("chart_id", sa.Uuid(as_uuid=True), sa.ForeignKey("personnel_org_chart.id"), nullable=False),
            sa.Column("parent_id", sa.Uuid(as_uuid=True), sa.ForeignKey("personnel_org_node.id"), nullable=True),
            sa.Column("title", sa.String(200), nullable=False),
            sa.Column("role_title", sa.String(100), nullable=True),
            sa.Column("person_name", sa.String(100), nullable=True),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("email", sa.String(100), nullable=True),
            sa.Column("pos_x", sa.Float(), nullable=False, server_default="0"),
            sa.Column("pos_y", sa.Float(), nullable=False, server_default="0"),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_personnel_org_node_chart_id", "personnel_org_node", ["chart_id"])

    if not _table_exists("personnel_org_link"):
        op.create_table(
            "personnel_org_link",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("chart_id", sa.Uuid(as_uuid=True), sa.ForeignKey("personnel_org_chart.id"), nullable=False),
            sa.Column("source_node_id", sa.Uuid(as_uuid=True), sa.ForeignKey("personnel_org_node.id"), nullable=False),
            sa.Column("target_node_id", sa.Uuid(as_uuid=True), sa.ForeignKey("personnel_org_node.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.UniqueConstraint("chart_id", "source_node_id", "target_node_id", name="uk_personnel_org_link"),
        )
        op.create_index("ix_personnel_org_link_chart_id", "personnel_org_link", ["chart_id"])

    if not _table_exists("personnel_internal"):
        op.create_table(
            "personnel_internal",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("role_title", sa.String(100), nullable=False, server_default=""),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("email", sa.String(100), nullable=True),
            sa.Column("company", sa.String(200), nullable=True),
            sa.Column("project_no", sa.String(100), nullable=True),
            sa.Column("org_node_id", sa.Uuid(as_uuid=True), sa.ForeignKey("personnel_org_node.id"), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_personnel_internal_name", "personnel_internal", ["name"])
        op.create_index("ix_personnel_internal_project_no", "personnel_internal", ["project_no"])

    if not _table_exists("personnel_supplier"):
        op.create_table(
            "personnel_supplier",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("role_title", sa.String(100), nullable=False, server_default=""),
            sa.Column("phone", sa.String(50), nullable=True),
            sa.Column("email", sa.String(100), nullable=True),
            sa.Column("wechat", sa.String(100), nullable=True),
            sa.Column("manufacturer_id", sa.Uuid(as_uuid=True), sa.ForeignKey("manufacturer.id"), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_personnel_supplier_name", "personnel_supplier", ["name"])
        op.create_index("ix_personnel_supplier_manufacturer_id", "personnel_supplier", ["manufacturer_id"])

    if not _table_exists("personnel_supplier_contract"):
        op.create_table(
            "personnel_supplier_contract",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("supplier_id", sa.Uuid(as_uuid=True), sa.ForeignKey("personnel_supplier.id"), nullable=False),
            sa.Column("contract_id", sa.Uuid(as_uuid=True), sa.ForeignKey("device_contract.id"), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.UniqueConstraint("supplier_id", "contract_id", name="uk_personnel_supplier_contract"),
        )
        op.create_index("ix_personnel_supplier_contract_supplier_id", "personnel_supplier_contract", ["supplier_id"])
        op.create_index("ix_personnel_supplier_contract_contract_id", "personnel_supplier_contract", ["contract_id"])

    if not _table_exists("personnel_supplier_product"):
        op.create_table(
            "personnel_supplier_product",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column("supplier_id", sa.Uuid(as_uuid=True), sa.ForeignKey("personnel_supplier.id"), nullable=False),
            sa.Column("device_model_id", sa.Uuid(as_uuid=True), sa.ForeignKey("device_model.id"), nullable=True),
            sa.Column("device_name", sa.String(200), nullable=True),
            sa.Column("device_model_name", sa.String(200), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_personnel_supplier_product_supplier_id", "personnel_supplier_product", ["supplier_id"])

    # silence unused on sqlite
    _ = bind


def downgrade() -> None:
    for table in (
        "personnel_supplier_product",
        "personnel_supplier_contract",
        "personnel_supplier",
        "personnel_internal",
        "personnel_org_link",
        "personnel_org_node",
        "personnel_org_chart",
    ):
        if _table_exists(table):
            op.drop_table(table)
