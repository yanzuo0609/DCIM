"""Make rack code unique per room instead of globally."""

from alembic import op


revision = "0006_rack_code_unique_per_room"
down_revision = "0005_add_room_slot_codes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rack") as batch_op:
        batch_op.drop_constraint("uk_rack_code", type_="unique")
        batch_op.create_unique_constraint("uk_rack_room_code", ["room_id", "code"])


def downgrade() -> None:
    with op.batch_alter_table("rack") as batch_op:
        batch_op.drop_constraint("uk_rack_room_code", type_="unique")
        batch_op.create_unique_constraint("uk_rack_code", ["code"])
