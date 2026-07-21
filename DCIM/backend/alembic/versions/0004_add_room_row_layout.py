"""Add room row_layout JSON column."""

from alembic import op
import sqlalchemy as sa


revision = "0004_add_room_row_layout"
down_revision = "0003_add_room_rack_layout"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("room") as batch_op:
        batch_op.add_column(sa.Column("row_layout", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("room") as batch_op:
        batch_op.drop_column("row_layout")
