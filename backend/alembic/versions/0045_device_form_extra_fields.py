"""Add device form fields: project scope/app, warranty, mounted_at

Revision ID: 0045
Revises: 0044
Create Date: 2026-08-21
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0045_device_form_extra_fields"
down_revision: Union[str, None] = "0044_device_type_switch_split"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "device" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("device")}
    with op.batch_alter_table("device") as batch:
        if "project_scope" not in cols:
            batch.add_column(sa.Column("project_scope", sa.String(length=200), nullable=True))
        if "project_app" not in cols:
            batch.add_column(sa.Column("project_app", sa.String(length=200), nullable=True))
        if "warranty_years" not in cols:
            batch.add_column(sa.Column("warranty_years", sa.Integer(), nullable=True))
        if "mounted_at" not in cols:
            batch.add_column(sa.Column("mounted_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if "device" not in set(inspector.get_table_names()):
        return
    cols = {c["name"] for c in inspector.get_columns("device")}
    with op.batch_alter_table("device") as batch:
        if "mounted_at" in cols:
            batch.drop_column("mounted_at")
        if "warranty_years" in cols:
            batch.drop_column("warranty_years")
        if "project_app" in cols:
            batch.drop_column("project_app")
        if "project_scope" in cols:
            batch.drop_column("project_scope")
