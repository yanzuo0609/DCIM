"""Per-device network panel bind flag for apply/modify semantics."""

from alembic import op
import sqlalchemy as sa


revision = "0023_device_network_panel_bound"
down_revision = "0022_device_model_port_layout"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("device", "network_panel_bound"):
        with op.batch_alter_table("device") as batch_op:
            batch_op.add_column(
                sa.Column(
                    "network_panel_bound",
                    sa.Boolean(),
                    nullable=False,
                    server_default=sa.false(),
                )
            )


def downgrade() -> None:
    if _column_exists("device", "network_panel_bound"):
        with op.batch_alter_table("device") as batch_op:
            batch_op.drop_column("network_panel_bound")
