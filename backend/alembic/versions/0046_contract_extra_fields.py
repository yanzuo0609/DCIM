"""Add contract form extension fields.

Revision ID: 0046_contract_extra_fields
Revises: 0045_device_form_extra_fields
Create Date: 2026-08-21
"""

from alembic import op
import sqlalchemy as sa

revision = "0046_contract_extra_fields"
down_revision = "0045_device_form_extra_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("device_contract") as batch:
        batch.add_column(sa.Column("project_budget", sa.Numeric(14, 2), nullable=True))
        batch.add_column(sa.Column("purchase_org", sa.String(200), nullable=True))
        batch.add_column(sa.Column("fund_source", sa.String(100), nullable=True))
        batch.add_column(sa.Column("using_org", sa.String(100), nullable=True))
        batch.add_column(sa.Column("winning_bidder", sa.String(200), nullable=True))
        batch.add_column(sa.Column("signed_at", sa.Date(), nullable=True))
        batch.add_column(sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("device_contract") as batch:
        batch.drop_column("archived_at")
        batch.drop_column("signed_at")
        batch.drop_column("winning_bidder")
        batch.drop_column("using_org")
        batch.drop_column("fund_source")
        batch.drop_column("purchase_org")
        batch.drop_column("project_budget")
