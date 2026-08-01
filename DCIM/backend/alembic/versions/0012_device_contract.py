"""Add device_contract table and device.contract_id."""

from alembic import op
import sqlalchemy as sa


revision = "0012_device_contract"
down_revision = "0011_ip_address_status"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "device_contract",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("contract_no", sa.String(length=100), nullable=False),
        sa.Column("project_no", sa.String(length=100), nullable=True),
        sa.Column("device_items", sa.JSON(), nullable=True),
        sa.Column("device_names", sa.JSON(), nullable=True),
        sa.Column("device_model_names", sa.JSON(), nullable=True),
        sa.Column("manufacturer_names", sa.JSON(), nullable=True),
        sa.Column("device_name", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("device_model_name", sa.String(length=500), nullable=False, server_default=""),
        sa.Column("manufacturer_name", sa.String(length=500), nullable=True),
        sa.Column("device_model_id", sa.Uuid(), nullable=True),
        sa.Column("quantity", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("unit_price", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("contract_total", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("price_unit", sa.String(length=10), nullable=False, server_default="yuan"),
        sa.Column("purchase_date", sa.Date(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["device_model_id"], ["device_model.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("contract_no", name="uk_device_contract_no"),
    )
    op.create_index("ix_device_contract_device_model_id", "device_contract", ["device_model_id"])

    with op.batch_alter_table("device") as batch_op:
        batch_op.add_column(sa.Column("contract_id", sa.Uuid(), nullable=True))
        batch_op.create_index("ix_device_contract_id", ["contract_id"], unique=False)
        batch_op.create_foreign_key(
            "fk_device_contract_id",
            "device_contract",
            ["contract_id"],
            ["id"],
        )


def downgrade() -> None:
    with op.batch_alter_table("device") as batch_op:
        batch_op.drop_constraint("fk_device_contract_id", type_="foreignkey")
        batch_op.drop_index("ix_device_contract_id")
        batch_op.drop_column("contract_id")

    op.drop_index("ix_device_contract_device_model_id", table_name="device_contract")
    op.drop_table("device_contract")
