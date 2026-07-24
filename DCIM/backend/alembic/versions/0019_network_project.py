"""Make 0019 upgrade idempotent for DBs that already have tables via create_all."""

import uuid
from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "0019_network_project"
down_revision = "0018_network_node_port_layout"
branch_labels = None
depends_on = None


def _table_exists(name: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:n"),
        {"n": name},
    ).fetchall()
    return bool(rows)


def _column_exists(table: str, column: str) -> bool:
    bind = op.get_bind()
    rows = bind.execute(sa.text(f"PRAGMA table_info({table})")).fetchall()
    return any(r[1] == column for r in rows)


def upgrade() -> None:
    if not _table_exists("network_project"):
        op.create_table(
            "network_project",
            sa.Column("id", sa.Uuid(), nullable=False),
            sa.Column(
                "created_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("created_by", sa.Uuid(), nullable=True),
            sa.Column(
                "updated_at",
                sa.DateTime(timezone=True),
                server_default=sa.text("(CURRENT_TIMESTAMP)"),
                nullable=False,
            ),
            sa.Column("updated_by", sa.Uuid(), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
            sa.Column("code", sa.String(length=50), nullable=False),
            sa.Column("name", sa.String(length=100), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("code", name="uk_network_project_code"),
        )

    if _table_exists("network_topology") and not _column_exists("network_topology", "project_id"):
        with op.batch_alter_table("network_topology") as batch_op:
            batch_op.add_column(sa.Column("project_id", sa.Uuid(), nullable=True))
            batch_op.create_index("ix_network_topology_project_id", ["project_id"])
            batch_op.create_foreign_key(
                "fk_network_topology_project_id",
                "network_project",
                ["project_id"],
                ["id"],
            )

    conn = op.get_bind()
    topologies = conn.execute(
        sa.text(
            "SELECT id FROM network_topology WHERE deleted_at IS NULL AND project_id IS NULL"
        )
    ).fetchall()
    if topologies:
        existing = conn.execute(
            sa.text(
                "SELECT id FROM network_project WHERE code = :code AND deleted_at IS NULL"
            ),
            {"code": "DEFAULT"},
        ).fetchone()
        if existing:
            project_id = existing[0]
        else:
            project_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            conn.execute(
                sa.text(
                    """
                    INSERT INTO network_project
                      (id, created_at, updated_at, version, code, name, description)
                    VALUES
                      (:id, :now, :now, 1, :code, :name, :description)
                    """
                ),
                {
                    "id": project_id,
                    "now": now,
                    "code": "DEFAULT",
                    "name": "默认项目",
                    "description": "迁移自动创建，用于挂载已有拓扑",
                },
            )
        conn.execute(
            sa.text(
                """
                UPDATE network_topology
                SET project_id = :project_id
                WHERE deleted_at IS NULL AND project_id IS NULL
                """
            ),
            {"project_id": project_id},
        )


def downgrade() -> None:
    if _table_exists("network_topology") and _column_exists("network_topology", "project_id"):
        with op.batch_alter_table("network_topology") as batch_op:
            try:
                batch_op.drop_constraint("fk_network_topology_project_id", type_="foreignkey")
            except Exception:
                pass
            try:
                batch_op.drop_index("ix_network_topology_project_id")
            except Exception:
                pass
            batch_op.drop_column("project_id")
    if _table_exists("network_project"):
        op.drop_table("network_project")
