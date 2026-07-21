"""Allow multiple device names / models on device_contract."""

from alembic import op
import sqlalchemy as sa


revision = "0014_device_contract_multi_names"
down_revision = "0013_device_contract_manual_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.add_column(sa.Column("device_names", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("device_model_names", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.drop_column("device_model_names")
        batch_op.drop_column("device_names")
