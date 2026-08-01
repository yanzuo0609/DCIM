"""Add network_node.on_canvas for topology placement."""

from alembic import op
import sqlalchemy as sa


revision = "0020_network_node_on_canvas"
down_revision = "0019_network_project"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    if not _column_exists("network_node", "on_canvas"):
        with op.batch_alter_table("network_node") as batch_op:
            batch_op.add_column(
                sa.Column("on_canvas", sa.Boolean(), nullable=False, server_default=sa.text("1"))
            )


def downgrade() -> None:
    if _column_exists("network_node", "on_canvas"):
        with op.batch_alter_table("network_node") as batch_op:
            batch_op.drop_column("on_canvas")
