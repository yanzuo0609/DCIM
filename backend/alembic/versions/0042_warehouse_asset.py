"""warehouse asset ledger

Revision ID: 0042
Revises: 0041
Create Date: 2026-08-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0042_warehouse_asset"
down_revision: Union[str, None] = "0041_warehouse"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "warehouse" in tables:
        cols = {c["name"] for c in inspector.get_columns("warehouse")}
        if "asset_ledger_ready" not in cols:
            with op.batch_alter_table("warehouse") as batch:
                batch.add_column(
                    sa.Column(
                        "asset_ledger_ready",
                        sa.Boolean(),
                        nullable=False,
                        server_default=sa.text("1"),
                    )
                )

    if "warehouse_asset" not in tables:
        op.create_table(
            "warehouse_asset",
            sa.Column("warehouse_id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("name", sa.String(length=200), nullable=False),
            sa.Column("project", sa.String(length=200), nullable=True),
            sa.Column("application", sa.String(length=200), nullable=True),
            sa.Column("category", sa.String(length=30), nullable=False, server_default="other"),
            sa.Column("status", sa.String(length=30), nullable=False, server_default="new"),
            sa.Column("inbound_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column(
                "outbound_mode",
                sa.String(length=20),
                nullable=False,
                server_default="undetermined",
            ),
            sa.Column("outbound_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("owner_name", sa.String(length=100), nullable=True),
            sa.Column("owner_contact", sa.String(length=100), nullable=True),
            sa.Column("remark", sa.Text(), nullable=True),
            sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.ForeignKeyConstraint(["warehouse_id"], ["warehouse.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            "ix_warehouse_asset_warehouse_id",
            "warehouse_asset",
            ["warehouse_id"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "warehouse_asset" in tables:
        op.drop_index("ix_warehouse_asset_warehouse_id", table_name="warehouse_asset")
        op.drop_table("warehouse_asset")
    if "warehouse" in tables:
        cols = {c["name"] for c in inspector.get_columns("warehouse")}
        if "asset_ledger_ready" in cols:
            with op.batch_alter_table("warehouse") as batch:
                batch.drop_column("asset_ledger_ready")
