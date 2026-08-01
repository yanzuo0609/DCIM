"""default rack visual_style to classic

Revision ID: 0031_rack_visual_style_classic
Revises: 0030_rack_visual_style
Create Date: 2026-07-31
"""

from alembic import op
import sqlalchemy as sa


revision = "0031_rack_visual_style_classic"
down_revision = "0030_rack_visual_style"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 将此前默认 schematic 恢复为经典深色样式
    op.execute("UPDATE rack SET visual_style = 'classic' WHERE visual_style = 'schematic' OR visual_style IS NULL OR visual_style = ''")
    op.execute(
        "UPDATE rack_template SET visual_style = 'classic' WHERE visual_style = 'schematic' OR visual_style IS NULL OR visual_style = ''"
    )
    # SQLite: alter server default via batch if needed — keep column, app defaults handle new rows
    bind = op.get_bind()
    if bind.dialect.name != "sqlite":
        op.alter_column(
            "rack",
            "visual_style",
            existing_type=sa.String(length=30),
            server_default="classic",
            existing_nullable=False,
        )
        op.alter_column(
            "rack_template",
            "visual_style",
            existing_type=sa.String(length=30),
            server_default="classic",
            existing_nullable=False,
        )


def downgrade() -> None:
    op.execute("UPDATE rack SET visual_style = 'schematic' WHERE visual_style = 'classic'")
    op.execute("UPDATE rack_template SET visual_style = 'schematic' WHERE visual_style = 'classic'")
