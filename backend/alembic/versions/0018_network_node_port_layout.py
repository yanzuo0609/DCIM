"""Add network_node.port_layout for visual interface definition."""

from alembic import op
import sqlalchemy as sa


revision = "0018_network_node_port_layout"
down_revision = "0017_network_design"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("network_node") as batch_op:
        batch_op.add_column(sa.Column("port_layout", sa.JSON(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("network_node") as batch_op:
        batch_op.drop_column("port_layout")
