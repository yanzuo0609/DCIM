"""Store full device_items JSON and contract_total on device_contract."""

from alembic import op
import sqlalchemy as sa


revision = "0016_device_contract_items_total"
down_revision = "0015_device_contract_manufacturer_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.add_column(sa.Column("device_items", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("contract_total", sa.Numeric(14, 2), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.drop_column("contract_total")
        batch_op.drop_column("device_items")
