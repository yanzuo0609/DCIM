"""topology project model folder bind, design_model_id, lab session

Revision ID: 0035_topology_lab_integration
Revises: 0034_network_model_design
Create Date: 2026-08-07
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision = "0035_topology_lab_integration"
down_revision = "0034_network_model_design"
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
    bind = op.get_bind()
    json_type = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")

    if _table_exists("network_project") and not _column_exists("network_project", "model_root_folder_id"):
        op.add_column(
            "network_project",
            sa.Column("model_root_folder_id", sa.Uuid(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_network_project_model_root_folder",
            "network_project",
            "network_model_folder",
            ["model_root_folder_id"],
            ["id"],
        )
        op.create_index(
            "ix_network_project_model_root_folder_id",
            "network_project",
            ["model_root_folder_id"],
        )

    if _table_exists("network_node") and not _column_exists("network_node", "design_model_id"):
        op.add_column(
            "network_node",
            sa.Column("design_model_id", sa.Uuid(as_uuid=True), nullable=True),
        )
        op.create_foreign_key(
            "fk_network_node_design_model",
            "network_node",
            "network_design_model",
            ["design_model_id"],
            ["id"],
        )
        op.create_index(
            "ix_network_node_design_model_id",
            "network_node",
            ["design_model_id"],
        )

    if not _table_exists("network_lab_session"):
        op.create_table(
            "network_lab_session",
            sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
            sa.Column(
                "topology_id",
                sa.Uuid(as_uuid=True),
                sa.ForeignKey("network_topology.id"),
                nullable=False,
                unique=True,
            ),
            sa.Column("engine", sa.String(20), nullable=False, server_default="eve-ng"),
            sa.Column("external_lab_path", sa.String(500), nullable=True),
            sa.Column("status", sa.String(30), nullable=False, server_default="idle"),
            sa.Column("last_sync_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("node_map", json_type, nullable=True),
            sa.Column("node_status", json_type, nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("created_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
            sa.Column("updated_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("deleted_by", sa.Uuid(as_uuid=True), nullable=True),
            sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        )
        op.create_index("ix_network_lab_session_topology_id", "network_lab_session", ["topology_id"])


def downgrade() -> None:
    if _table_exists("network_lab_session"):
        op.drop_table("network_lab_session")
    if _column_exists("network_node", "design_model_id"):
        op.drop_index("ix_network_node_design_model_id", table_name="network_node")
        op.drop_constraint("fk_network_node_design_model", "network_node", type_="foreignkey")
        op.drop_column("network_node", "design_model_id")
    if _column_exists("network_project", "model_root_folder_id"):
        op.drop_index("ix_network_project_model_root_folder_id", table_name="network_project")
        op.drop_constraint("fk_network_project_model_root_folder", "network_project", type_="foreignkey")
        op.drop_column("network_project", "model_root_folder_id")
