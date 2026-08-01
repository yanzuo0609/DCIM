"""Per-item manufacturer names on device_contract."""

from alembic import op
import sqlalchemy as sa


revision = "0015_device_contract_manufacturer_names"
down_revision = "0014_device_contract_multi_names"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.add_column(sa.Column("manufacturer_names", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.drop_column("manufacturer_names")
