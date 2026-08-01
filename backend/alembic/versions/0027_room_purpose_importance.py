"""add room purpose and importance

Revision ID: 0027_room_purpose_importance
Revises: 0026_room_pillar_layout
Create Date: 2026-07-30
"""

from alembic import op
import sqlalchemy as sa


revision = "0027_room_purpose_importance"
down_revision = "0026_room_pillar_layout"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("room", "purpose"):
        op.add_column(
            "room",
            sa.Column("purpose", sa.String(length=50), nullable=True, server_default="production"),
        )
    if not _column_exists("room", "importance"):
        op.add_column(
            "room",
            sa.Column("importance", sa.String(length=20), nullable=True, server_default="medium"),
        )


def downgrade() -> None:
    if _column_exists("room", "importance"):
        op.drop_column("room", "importance")
    if _column_exists("room", "purpose"):
        op.drop_column("room", "purpose")
