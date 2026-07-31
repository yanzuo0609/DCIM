"""add rack visual_style

Revision ID: 0030_rack_visual_style
Revises: 0029_room_outline_attributes
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0030_rack_visual_style"
down_revision = "0029_room_outline_attributes"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("rack_template", "visual_style"):
        op.add_column(
            "rack_template",
            sa.Column(
                "visual_style",
                sa.String(length=30),
                nullable=False,
                server_default="schematic",
            ),
        )
    if not _column_exists("rack", "visual_style"):
        op.add_column(
            "rack",
            sa.Column(
                "visual_style",
                sa.String(length=30),
                nullable=False,
                server_default="schematic",
            ),
        )


def downgrade() -> None:
    if _column_exists("rack", "visual_style"):
        op.drop_column("rack", "visual_style")
    if _column_exists("rack_template", "visual_style"):
        op.drop_column("rack_template", "visual_style")
