"""IP address segments (pools) as first-class list rows."""

from alembic import op
import sqlalchemy as sa


revision = "0024_ip_segment"
down_revision = "0023_device_network_panel_bound"
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
        op.create_table(
            "ip_segment",
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("start_ip", sa.String(length=64), nullable=False),
            sa.Column("end_ip", sa.String(length=64), nullable=False),
            sa.Column("netmask", sa.String(length=64), nullable=True),
            sa.Column("gateway", sa.String(length=64), nullable=True),
            sa.Column("dns", sa.String(length=64), nullable=True),
            sa.Column("dns_secondary", sa.String(length=64), nullable=True),
            sa.Column("application_type", sa.String(length=50), nullable=True),
            sa.Column("label", sa.String(length=100), nullable=True),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_by", sa.Uuid(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_ip_segment_start_ip", "ip_segment", ["start_ip"])
        op.create_index("ix_ip_segment_end_ip", "ip_segment", ["end_ip"])
        op.create_index("ix_ip_segment_application_type", "ip_segment", ["application_type"])

    if _table_exists("ip_address") and not _column_exists("ip_address", "segment_id"):
        with op.batch_alter_table("ip_address") as batch_op:
            batch_op.add_column(sa.Column("segment_id", sa.Uuid(), nullable=True))
            batch_op.create_index("ix_ip_address_segment_id", ["segment_id"])
            batch_op.create_foreign_key(
                "fk_ip_address_segment_id",
                "ip_segment",
                ["segment_id"],
                ["id"],
            )


def downgrade() -> None:
    if _table_exists("ip_address") and _column_exists("ip_address", "segment_id"):
        with op.batch_alter_table("ip_address") as batch_op:
            batch_op.drop_constraint("fk_ip_address_segment_id", type_="foreignkey")
            batch_op.drop_index("ix_ip_address_segment_id")
            batch_op.drop_column("segment_id")
    if _table_exists("ip_segment"):
        op.drop_index("ix_ip_segment_application_type", table_name="ip_segment")
        op.drop_index("ix_ip_segment_end_ip", table_name="ip_segment")
        op.drop_index("ix_ip_segment_start_ip", table_name="ip_segment")
        op.drop_table("ip_segment")
