"""Add network_link design fields: labels, cable, interface class, link role."""

from alembic import op
import sqlalchemy as sa


revision = "0021_network_link_design_fields"
down_revision = "0020_network_node_on_canvas"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    cols = [
        ("source_label", sa.String(200)),
        ("target_label", sa.String(200)),
        ("cable_type", sa.String(30)),
        ("interface_class", sa.String(30)),
        ("link_role", sa.String(30)),
    ]
    for name, col_type in cols:
        if not _column_exists("network_link", name):
            with op.batch_alter_table("network_link") as batch_op:
                batch_op.add_column(sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    for name in ("source_label", "target_label", "cable_type", "interface_class", "link_role"):
        if _column_exists("network_link", name):
            with op.batch_alter_table("network_link") as batch_op:
                batch_op.drop_column(name)
