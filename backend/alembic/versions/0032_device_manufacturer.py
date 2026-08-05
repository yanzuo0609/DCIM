"""add device-level manufacturer override

Revision ID: 0032_device_manufacturer
Revises: 0031_rack_visual_style_classic
Create Date: 2026-08-05
"""

from alembic import op
import sqlalchemy as sa


revision = "0032_device_manufacturer"
down_revision = "0031_rack_visual_style_classic"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("device", "manufacturer_id"):
        op.add_column(
            "device",
            sa.Column("manufacturer_id", sa.Uuid(as_uuid=True), nullable=True),
        )
        op.create_index("ix_device_manufacturer_id", "device", ["manufacturer_id"])
        bind = op.get_bind()
        if bind.dialect.name != "sqlite":
            op.create_foreign_key(
                "fk_device_manufacturer_id",
                "device",
                "manufacturer",
                ["manufacturer_id"],
                ["id"],
            )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.drop_constraint("fk_device_manufacturer_id", "device", type_="foreignkey")
    if _column_exists("device", "manufacturer_id"):
        op.drop_index("ix_device_manufacturer_id", table_name="device")
        op.drop_column("device", "manufacturer_id")
