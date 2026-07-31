"""Add room rack code fields."""

from alembic import op
import sqlalchemy as sa


revision = "0005_add_room_slot_codes"
down_revision = "0004_add_room_row_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("room") as batch_op:
        batch_op.add_column(
            sa.Column("code_mode", sa.String(length=20), nullable=False, server_default="auto")
        )
        batch_op.add_column(sa.Column("code_prefix", sa.String(length=50), nullable=True))
        batch_op.add_column(sa.Column("slot_codes", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("room") as batch_op:
        batch_op.drop_column("slot_codes")
        batch_op.drop_column("code_prefix")
        batch_op.drop_column("code_mode")
