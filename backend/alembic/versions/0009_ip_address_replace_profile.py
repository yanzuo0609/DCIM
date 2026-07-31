"""Replace IP profiles with ip_address records."""

from alembic import op
import sqlalchemy as sa


revision = "0009_ip_address"
down_revision = "0008_bmc_profile"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ip_address",
        sa.Column("system_ip", sa.String(length=64), nullable=False),
        sa.Column("bmc_ip", sa.String(length=64), nullable=True),
        sa.Column("vip", sa.String(length=64), nullable=True),
        sa.Column("label", sa.String(length=100), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("bind_type", sa.String(length=20), nullable=False, server_default="none"),
        sa.Column("device_id", sa.Uuid(), nullable=True),
        sa.Column("rack_id", sa.Uuid(), nullable=True),
        sa.Column("room_id", sa.Uuid(), nullable=True),
        sa.Column("scope_rack_ids", sa.JSON(), nullable=True),
        sa.Column("u_position", sa.Integer(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["device_id"], ["device.id"]),
        sa.ForeignKeyConstraint(["rack_id"], ["rack.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["room.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("system_ip", name="uk_ip_address_system_ip"),
    )
    op.create_index("ix_ip_address_system_ip", "ip_address", ["system_ip"])
    op.create_index("ix_ip_address_bmc_ip", "ip_address", ["bmc_ip"])
    op.create_index("ix_ip_address_vip", "ip_address", ["vip"])
    op.create_index("ix_ip_address_device_id", "ip_address", ["device_id"])
    op.create_index("ix_ip_address_rack_id", "ip_address", ["rack_id"])
    op.create_index("ix_ip_address_room_id", "ip_address", ["room_id"])

    with op.batch_alter_table("device") as batch_op:
        batch_op.drop_index("ix_device_ip_profile_id")
        batch_op.drop_constraint("fk_device_ip_profile", type_="foreignkey")
        batch_op.drop_column("ip_profile_id")

    op.drop_table("device_ip_profile")


def downgrade() -> None:
    op.create_table(
        "device_ip_profile",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("primary_ip", sa.String(length=64), nullable=True),
        sa.Column("addresses", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_device_ip_profile_code"),
    )
    with op.batch_alter_table("device") as batch_op:
        batch_op.add_column(sa.Column("ip_profile_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_device_ip_profile", "device_ip_profile", ["ip_profile_id"], ["id"]
        )
        batch_op.create_index("ix_device_ip_profile_id", ["ip_profile_id"])

    op.drop_table("ip_address")
