"""add rack app_usage and app_color

Revision ID: 0028_rack_app_usage_color
Revises: 0027_room_purpose_importance
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0028_rack_app_usage_color"
down_revision = "0027_room_purpose_importance"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("rack", "app_usage"):
        op.add_column(
            "rack",
            sa.Column("app_usage", sa.String(length=100), nullable=True),
        )
    if not _column_exists("rack", "app_color"):
        op.add_column(
            "rack",
            sa.Column("app_color", sa.String(length=20), nullable=True),
        )


def downgrade() -> None:
    if _column_exists("rack", "app_color"):
        op.drop_column("rack", "app_color")
    if _column_exists("rack", "app_usage"):
        op.drop_column("rack", "app_usage")
