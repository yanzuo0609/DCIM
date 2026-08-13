"""Scope wiring rules to network project (shared across topologies).

Revision ID: 0038_wiring_rule_project_scope
Revises: 0037_node_device_groups
Create Date: 2026-08-12
"""

from alembic import op
import sqlalchemy as sa


revision = "0038_wiring_rule_project_scope"
down_revision = "0037_node_device_groups"
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


def _index_exists(name: str) -> bool:
    bind = op.get_bind()
    insp = sa.inspect(bind)
    for table in insp.get_table_names():
        for idx in insp.get_indexes(table):
            if idx.get("name") == name:
                return True
    return False


def upgrade() -> None:
    if not _table_exists("network_wiring_rule"):
        return

    if not _column_exists("network_wiring_rule", "project_id"):
        op.add_column(
            "network_wiring_rule",
            sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=True),
        )

    # Backfill project_id from topology.project_id
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE network_wiring_rule
            SET project_id = (
              SELECT network_topology.project_id
              FROM network_topology
              WHERE network_topology.id = network_wiring_rule.topology_id
            )
            WHERE project_id IS NULL
              AND topology_id IS NOT NULL
            """
        )
    )

    if not _index_exists("ix_network_wiring_rule_project_id"):
        op.create_index(
            "ix_network_wiring_rule_project_id",
            "network_wiring_rule",
            ["project_id"],
        )


def downgrade() -> None:
    if not _table_exists("network_wiring_rule"):
        return
    if _index_exists("ix_network_wiring_rule_project_id"):
        op.drop_index("ix_network_wiring_rule_project_id", table_name="network_wiring_rule")
    if _column_exists("network_wiring_rule", "project_id"):
        op.drop_column("network_wiring_rule", "project_id")
