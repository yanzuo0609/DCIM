"""Add device types, association profiles, and device name/type/profile FKs."""

from alembic import op
import sqlalchemy as sa


revision = "0007_device_types_and_profiles"
down_revision = "0006_rack_code_unique_per_room"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_type",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_device_type_code"),
    )
    op.create_table(
        "device_param_profile",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_device_param_profile_code"),
    )
    op.create_table(
        "device_system_profile",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_device_system_profile_code"),
    )
    op.create_table(
        "device_ip_profile",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("primary_ip", sa.String(length=64), nullable=True),
        sa.Column("addresses", sa.JSON(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_device_ip_profile_code"),
    )
    with op.batch_alter_table("device") as batch_op:
        batch_op.add_column(sa.Column("name", sa.String(length=100), nullable=True))
        batch_op.add_column(sa.Column("device_type_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("param_profile_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("system_profile_id", sa.Uuid(), nullable=True))
        batch_op.add_column(sa.Column("ip_profile_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key("fk_device_type", "device_type", ["device_type_id"], ["id"])
        batch_op.create_foreign_key("fk_device_param_profile", "device_param_profile", ["param_profile_id"], ["id"])
        batch_op.create_foreign_key("fk_device_system_profile", "device_system_profile", ["system_profile_id"], ["id"])
        batch_op.create_foreign_key("fk_device_ip_profile", "device_ip_profile", ["ip_profile_id"], ["id"])
        batch_op.create_index("ix_device_device_type_id", ["device_type_id"])
        batch_op.create_index("ix_device_param_profile_id", ["param_profile_id"])
        batch_op.create_index("ix_device_system_profile_id", ["system_profile_id"])
        batch_op.create_index("ix_device_ip_profile_id", ["ip_profile_id"])


def downgrade() -> None:
    with op.batch_alter_table("device") as batch_op:
        batch_op.drop_index("ix_device_ip_profile_id")
        batch_op.drop_index("ix_device_system_profile_id")
        batch_op.drop_index("ix_device_param_profile_id")
        batch_op.drop_index("ix_device_device_type_id")
        batch_op.drop_constraint("fk_device_ip_profile", type_="foreignkey")
        batch_op.drop_constraint("fk_device_system_profile", type_="foreignkey")
        batch_op.drop_constraint("fk_device_param_profile", type_="foreignkey")
        batch_op.drop_constraint("fk_device_type", type_="foreignkey")
        batch_op.drop_column("ip_profile_id")
        batch_op.drop_column("system_profile_id")
        batch_op.drop_column("param_profile_id")
        batch_op.drop_column("device_type_id")
        batch_op.drop_column("name")
    op.drop_table("device_ip_profile")
    op.drop_table("device_system_profile")
    op.drop_table("device_param_profile")
    op.drop_table("device_type")
