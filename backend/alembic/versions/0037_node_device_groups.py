"""Add network_node.device_groups JSON for multi-group membership."""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = "0037_node_device_groups"
down_revision = "0036_wiring_rule_engine"
branch_labels = None
depends_on = None


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    return any(c["name"] == column for c in inspector.get_columns(table))


def upgrade() -> None:
    if not _column_exists("network_node", "device_groups"):
        op.add_column("network_node", sa.Column("device_groups", sa.JSON(), nullable=True))
    # 回填：单组 → 数组
    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "sqlite":
        bind.exec_driver_sql(
            """
            UPDATE network_node
            SET device_groups = json_array(device_group)
            WHERE device_group IS NOT NULL
              AND TRIM(device_group) != ''
              AND (device_groups IS NULL OR device_groups = 'null')
            """
        )
    else:
        # MySQL / Postgres 兼容尽力回填
        try:
            bind.exec_driver_sql(
                """
                UPDATE network_node
                SET device_groups = JSON_ARRAY(device_group)
                WHERE device_group IS NOT NULL
                  AND TRIM(device_group) != ''
                  AND device_groups IS NULL
                """
            )
        except Exception:
            pass


def downgrade() -> None:
    if _column_exists("network_node", "device_groups"):
        op.drop_column("network_node", "device_groups")
