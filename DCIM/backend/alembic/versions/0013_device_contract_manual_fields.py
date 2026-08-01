"""Contract info: manual device_name / device_model_name fields."""

from alembic import op
import sqlalchemy as sa


revision = "0013_device_contract_manual_fields"
down_revision = "0012_device_contract"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.add_column(
            sa.Column("device_name", sa.String(length=100), nullable=False, server_default="")
        )
        batch_op.add_column(
            sa.Column(
                "device_model_name", sa.String(length=100), nullable=False, server_default=""
            )
        )
        batch_op.add_column(sa.Column("manufacturer_name", sa.String(length=100), nullable=True))
        batch_op.add_column(
            sa.Column("price_unit", sa.String(length=10), nullable=False, server_default="yuan")
        )

    # 从关联型号回填手工字段（兼容旧数据）
    op.execute(
        """
        UPDATE device_contract
        SET device_model_name = (
            SELECT name FROM device_model WHERE device_model.id = device_contract.device_model_id
        )
        WHERE (device_model_name IS NULL OR device_model_name = '')
          AND device_model_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE device_contract
        SET manufacturer_name = (
            SELECT m.name
            FROM device_model dm
            JOIN manufacturer m ON m.id = dm.manufacturer_id
            WHERE dm.id = device_contract.device_model_id
        )
        WHERE manufacturer_name IS NULL
          AND device_model_id IS NOT NULL
        """
    )
    op.execute(
        """
        UPDATE device_contract
        SET device_name = device_model_name
        WHERE device_name IS NULL OR device_name = ''
        """
    )

    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.alter_column(
            "device_model_id",
            existing_type=sa.Uuid(),
            nullable=True,
        )


def downgrade() -> None:
    with op.batch_alter_table("device_contract") as batch_op:
        batch_op.drop_column("price_unit")
        batch_op.drop_column("manufacturer_name")
        batch_op.drop_column("device_model_name")
        batch_op.drop_column("device_name")
