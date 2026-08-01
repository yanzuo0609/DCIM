"""add room pillar_layout for 3D end-aligned pillars

Revision ID: 0026_room_pillar_layout
Revises: 0025_ip_segment_ledger
Create Date: 2026-07-29
"""

from alembic import op
import sqlalchemy as sa


revision = "0026_room_pillar_layout"
down_revision = "0025_ip_segment_ledger"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return column in {c["name"] for c in insp.get_columns(table)}


def upgrade() -> None:
    if not _column_exists("room", "pillar_layout"):
        op.add_column("room", sa.Column("pillar_layout", sa.JSON(), nullable=True))


def downgrade() -> None:
    if _column_exists("room", "pillar_layout"):
        op.drop_column("room", "pillar_layout")
