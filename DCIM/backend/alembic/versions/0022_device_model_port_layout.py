"""Link device definition panels to catalog models / contract device names."""

from alembic import op
import sqlalchemy as sa


revision = "0022_device_model_port_layout"
down_revision = "0021_network_link_design_fields"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("device_model", "port_layout"):
        with op.batch_alter_table("device_model") as batch_op:
            batch_op.add_column(sa.Column("port_layout", sa.JSON(), nullable=True))
    if not _column_exists("device_model", "apply_device_name"):
        with op.batch_alter_table("device_model") as batch_op:
            batch_op.add_column(sa.Column("apply_device_name", sa.String(100), nullable=True))
    if not _column_exists("device_model", "network_kind"):
        with op.batch_alter_table("device_model") as batch_op:
            batch_op.add_column(sa.Column("network_kind", sa.String(20), nullable=True))

    if not _column_exists("network_node", "device_model_id"):
        with op.batch_alter_table("network_node") as batch_op:
            batch_op.add_column(
                sa.Column("device_model_id", sa.Uuid(as_uuid=True), nullable=True)
            )
            batch_op.create_index("ix_network_node_device_model_id", ["device_model_id"])
    if not _column_exists("network_node", "contract_device_name"):
        with op.batch_alter_table("network_node") as batch_op:
            batch_op.add_column(sa.Column("contract_device_name", sa.String(100), nullable=True))


def downgrade() -> None:
    if _column_exists("network_node", "contract_device_name"):
        with op.batch_alter_table("network_node") as batch_op:
            batch_op.drop_column("contract_device_name")
    if _column_exists("network_node", "device_model_id"):
        with op.batch_alter_table("network_node") as batch_op:
            batch_op.drop_index("ix_network_node_device_model_id")
            batch_op.drop_column("device_model_id")
    for name in ("network_kind", "apply_device_name", "port_layout"):
        if _column_exists("device_model", name):
            with op.batch_alter_table("device_model") as batch_op:
                batch_op.drop_column(name)
