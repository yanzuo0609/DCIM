"""add room outline and attributes

Revision ID: 0029_room_outline_attributes
Revises: 0028_rack_app_usage_color
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0029_room_outline_attributes"
down_revision = "0028_rack_app_usage_color"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("room", "outline_rows"):
        op.add_column(
            "room",
            sa.Column("outline_rows", sa.Integer(), nullable=False, server_default="8"),
        )
    if not _column_exists("room", "outline_cols"):
        op.add_column(
            "room",
            sa.Column("outline_cols", sa.Integer(), nullable=False, server_default="10"),
        )
    if not _column_exists("room", "attributes"):
        op.add_column(
            "room",
            sa.Column("attributes", sa.JSON(), nullable=True),
        )

    # 历史数据：轮廓对齐现有机柜网格
    op.execute(
        """
        UPDATE room
        SET outline_rows = CASE
              WHEN rack_rows IS NULL OR rack_rows < 1 THEN 8
              WHEN rack_rows > 50 THEN 50
              ELSE rack_rows
            END,
            outline_cols = CASE
              WHEN rack_columns IS NULL OR rack_columns < 1 THEN 10
              WHEN rack_columns > 50 THEN 50
              ELSE rack_columns
            END
        WHERE outline_rows IS NOT NULL
        """
    )


def downgrade() -> None:
    if _column_exists("room", "attributes"):
        op.drop_column("room", "attributes")
    if _column_exists("room", "outline_cols"):
        op.drop_column("room", "outline_cols")
    if _column_exists("room", "outline_rows"):
        op.drop_column("room", "outline_rows")
