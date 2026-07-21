"""Add netmask/gateway/dns fields to ip_address."""

from alembic import op
import sqlalchemy as sa


revision = "0010_ip_network_fields"
down_revision = "0009_ip_address"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ip_address") as batch_op:
        batch_op.add_column(sa.Column("netmask", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("gateway", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("dns", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("dns_secondary", sa.String(length=64), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("ip_address") as batch_op:
        batch_op.drop_column("dns_secondary")
        batch_op.drop_column("dns")
        batch_op.drop_column("gateway")
        batch_op.drop_column("netmask")
