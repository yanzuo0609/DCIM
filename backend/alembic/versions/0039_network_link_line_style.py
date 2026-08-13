"""Add network_link.line_style for topology canvas routing.

Revision ID: 0039_network_link_line_style
Revises: 0038_wiring_rule_project_scope
Create Date: 2026-08-13
"""

from alembic import op
import sqlalchemy as sa


revision = "0039_network_link_line_style"
down_revision = "0038_wiring_rule_project_scope"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if not _column_exists("network_link", "line_style"):
        op.add_column("network_link", sa.Column("line_style", sa.String(40), nullable=True))


def downgrade() -> None:
    if _column_exists("network_link", "line_style"):
        op.drop_column("network_link", "line_style")
