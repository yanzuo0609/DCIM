"""Create warehouse table linked to room.

Revision ID: 0041_warehouse
Revises: 0040_room_code_rack_seq_no
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa


revision = "0041_warehouse"
down_revision = "0040_room_code_rack_seq_no"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return name in insp.get_table_names()


def upgrade() -> None:
    if _table_exists("warehouse"):
        return
    op.create_table(
        "warehouse",
        sa.Column("room_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.String(length=50), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_by", sa.Uuid(), nullable=True),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("deleted_by", sa.Uuid(), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["room_id"], ["room.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uk_warehouse_code"),
    )
    op.create_index("ix_warehouse_room_id", "warehouse", ["room_id"])


def downgrade() -> None:
    if _table_exists("warehouse"):
        op.drop_index("ix_warehouse_room_id", table_name="warehouse")
        op.drop_table("warehouse")
