"""Add room rack layout columns."""

from alembic import op
import sqlalchemy as sa


revision = "0003_add_room_rack_layout"
down_revision = "0002_add_rack_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("room") as batch_op:
        batch_op.add_column(sa.Column("rack_rows", sa.Integer(), nullable=False, server_default="4"))
        batch_op.add_column(sa.Column("rack_columns", sa.Integer(), nullable=False, server_default="6"))


def downgrade() -> None:
    with op.batch_alter_table("room") as batch_op:
        batch_op.drop_column("rack_columns")
        batch_op.drop_column("rack_rows")
