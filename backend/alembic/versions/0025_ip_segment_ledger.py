"""Extend ip_segment with ledger fields matching address-segment table."""

from alembic import op
import sqlalchemy as sa


revision = "0025_ip_segment_ledger"
down_revision = "0024_ip_segment"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _table_exists("ip_segment"):
        return
    cols = [
        ("application", sa.String(100), True),
        ("network", sa.String(64), True),
        ("prefix_len", sa.Integer(), True),
        ("address_purpose", sa.String(50), True),
        ("network_type", sa.String(50), True),
        ("location", sa.String(100), True),
        ("remarks", sa.Text(), True),
    ]
    with op.batch_alter_table("ip_segment") as batch_op:
        for name, col_type, nullable in cols:
            if not _column_exists("ip_segment", name):
                batch_op.add_column(sa.Column(name, col_type, nullable=nullable))
    op.execute(
        """
        UPDATE ip_segment
        SET network = COALESCE(network, start_ip),
            prefix_len = COALESCE(prefix_len, 24),
            address_purpose = COALESCE(address_purpose, application_type),
            remarks = COALESCE(remarks, description)
        WHERE deleted_at IS NULL
        """
    )


def downgrade() -> None:
    if not _table_exists("ip_segment"):
        return
    with op.batch_alter_table("ip_segment") as batch_op:
        for name in (
            "application",
            "network",
            "prefix_len",
            "address_purpose",
            "network_type",
            "location",
            "remarks",
        ):
            if _column_exists("ip_segment", name):
                batch_op.drop_column(name)
