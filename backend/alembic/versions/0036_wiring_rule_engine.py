"""wiring rule engine: node role/group, link design fields

Revision ID: 0036_wiring_rule_engine
Revises: 0035_topology_lab_integration
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa


revision = "0036_wiring_rule_engine"
down_revision = "0035_topology_lab_integration"
branch_labels = None
depends_on = None


def _table_exists(table: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    return table in insp.get_table_names()


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    if table not in insp.get_table_names():
        return False
    return any(c["name"] == column for c in insp.get_columns(table))


def upgrade() -> None:
    if _table_exists("network_node"):
        if not _column_exists("network_node", "network_role"):
            op.add_column("network_node", sa.Column("network_role", sa.String(20), nullable=True))
        if not _column_exists("network_node", "device_group"):
            op.add_column("network_node", sa.Column("device_group", sa.String(80), nullable=True))

    if _table_exists("network_link"):
        cols = [
            ("connection_type", sa.String(30)),
            ("speed", sa.String(20)),
            ("lag_group", sa.String(80)),
            ("redundancy_path", sa.String(10)),
            ("media", sa.String(30)),
            ("module", sa.String(80)),
            ("cable_length_m", sa.Float()),
            ("wiring_rule_id", sa.Uuid(as_uuid=True)),
        ]
        for name, col_type in cols:
            if not _column_exists("network_link", name):
                op.add_column("network_link", sa.Column(name, col_type, nullable=True))


def downgrade() -> None:
    if _table_exists("network_link"):
        for name in (
            "wiring_rule_id",
            "cable_length_m",
            "module",
            "media",
            "redundancy_path",
            "lag_group",
            "speed",
            "connection_type",
        ):
            if _column_exists("network_link", name):
                op.drop_column("network_link", name)
    if _table_exists("network_node"):
        for name in ("device_group", "network_role"):
            if _column_exists("network_node", name):
                op.drop_column("network_node", name)
