"""Add status column to ip_address."""

from alembic import op
import sqlalchemy as sa


revision = "0011_ip_address_status"
down_revision = "0010_ip_network_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("ip_address") as batch_op:
        batch_op.add_column(
            sa.Column("status", sa.String(length=20), nullable=False, server_default="free")
        )
        batch_op.create_index("ix_ip_address_status", ["status"], unique=False)

    # 已有绑定关系的地址标为已分配
    op.execute(
        """
        UPDATE ip_address
        SET status = 'allocated'
        WHERE deleted_at IS NULL
          AND (
            device_id IS NOT NULL
            OR bind_type IN ('device', 'rack', 'rack_range')
          )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("ip_address") as batch_op:
        batch_op.drop_index("ix_ip_address_status")
        batch_op.drop_column("status")
