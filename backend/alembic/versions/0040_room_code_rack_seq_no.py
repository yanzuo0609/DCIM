"""Add room.code and rack.seq_no for unique IDs / sequential numbering.

Revision ID: 0040_room_code_rack_seq_no
Revises: 0039_network_link_line_style
Create Date: 2026-08-20
"""

from alembic import op
import sqlalchemy as sa


revision = "0040_room_code_rack_seq_no"
down_revision = "0039_network_link_line_style"
branch_labels = None
depends_on = None


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
        for uk in insp.get_unique_constraints(table):
            if uk.get("name") == name:
                return True
    return False


def upgrade() -> None:
    if not _column_exists("room", "code"):
        op.add_column(
            "room",
            sa.Column("code", sa.String(length=50), nullable=False, server_default=""),
        )
    if not _index_exists("uk_room_code"):
        # Backfill CR1、CR2… before unique index
        conn = op.get_bind()
        rows = conn.execute(
            sa.text(
                "SELECT id, code FROM room WHERE deleted_at IS NULL "
                "ORDER BY created_at ASC, name ASC"
            )
        ).fetchall()
        import re

        cr_re = re.compile(r"^CR(\d+)$", re.IGNORECASE)
        used: set[str] = set()
        max_n = 0
        need_ids: list = []
        for row in rows:
            rid, code = row[0], row[1]
            raw = str(code or "").strip().upper()
            m = cr_re.match(raw)
            if m:
                used.add(raw)
                max_n = max(max_n, int(m.group(1)))
            else:
                need_ids.append(rid)
        for rid in need_ids:
            max_n += 1
            code = f"CR{max_n}"
            while code in used:
                max_n += 1
                code = f"CR{max_n}"
            used.add(code)
            conn.execute(
                sa.text("UPDATE room SET code = :code WHERE id = :id"),
                {"code": code, "id": rid},
            )
        op.create_unique_constraint("uk_room_code", "room", ["code"])

    if not _column_exists("rack", "seq_no"):
        op.add_column("rack", sa.Column("seq_no", sa.Integer(), nullable=True))
    if not _index_exists("uk_rack_room_seq_no"):
        op.create_unique_constraint("uk_rack_room_seq_no", "rack", ["room_id", "seq_no"])


def downgrade() -> None:
    if _index_exists("uk_rack_room_seq_no"):
        op.drop_constraint("uk_rack_room_seq_no", "rack", type_="unique")
    if _column_exists("rack", "seq_no"):
        op.drop_column("rack", "seq_no")
    if _index_exists("uk_room_code"):
        op.drop_constraint("uk_room_code", "room", type_="unique")
    if _column_exists("room", "code"):
        op.drop_column("room", "code")
