"""Add BMC profiles and device.bmc_profile_id."""

from alembic import op
import sqlalchemy as sa


revision = "0008_bmc_profile"
down_revision = "0007_device_types_and_profiles"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_bmc_profile",
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
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
        sa.UniqueConstraint("code", name="uk_device_bmc_profile_code"),
    )
    with op.batch_alter_table("device") as batch_op:
        batch_op.add_column(sa.Column("bmc_profile_id", sa.Uuid(), nullable=True))
        batch_op.create_foreign_key(
            "fk_device_bmc_profile", "device_bmc_profile", ["bmc_profile_id"], ["id"]
        )
        batch_op.create_index("ix_device_bmc_profile_id", ["bmc_profile_id"])


def downgrade() -> None:
    with op.batch_alter_table("device") as batch_op:
        batch_op.drop_index("ix_device_bmc_profile_id")
        batch_op.drop_constraint("fk_device_bmc_profile", type_="foreignkey")
        batch_op.drop_column("bmc_profile_id")
    op.drop_table("device_bmc_profile")
