"""warehouse asset quantity and unit

Revision ID: 0043
Revises: 0042
Create Date: 2026-08-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0043_warehouse_asset_quantity"
down_revision: Union[str, None] = "0042_warehouse_asset"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "warehouse_asset" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("warehouse_asset")}
    with op.batch_alter_table("warehouse_asset") as batch:
        if "quantity" not in cols:
            batch.add_column(
                sa.Column("quantity", sa.Integer(), nullable=False, server_default="1")
            )
        if "unit" not in cols:
            batch.add_column(
                sa.Column("unit", sa.String(length=20), nullable=False, server_default="piece")
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "warehouse_asset" not in tables:
        return
    cols = {c["name"] for c in inspector.get_columns("warehouse_asset")}
    with op.batch_alter_table("warehouse_asset") as batch:
        if "unit" in cols:
            batch.drop_column("unit")
        if "quantity" in cols:
            batch.drop_column("quantity")
