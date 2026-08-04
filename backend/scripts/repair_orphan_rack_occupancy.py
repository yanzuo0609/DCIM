"""Clear orphaned rack occupancy pointing at soft-deleted / missing devices."""
from __future__ import annotations

import sqlite3
from pathlib import Path

DB = Path(__file__).resolve().parents[1] / "rackdcim.db"


def main() -> None:
    conn = sqlite3.connect(DB)
    conn.row_factory = sqlite3.Row
    cur = conn.cursor()

    # Target AB02 in room 303 first (user-reported), then all orphans.
    targets = cur.execute(
        """
        SELECT p.id AS pos_id, p.rack_id, p.u_position, p.device_id, r.code, rm.name AS room
        FROM rack_position p
        JOIN rack r ON r.id = p.rack_id
        JOIN room rm ON rm.id = r.room_id
        LEFT JOIN device d ON d.id = p.device_id
        WHERE p.deleted_at IS NULL
          AND p.occupied = 1
          AND (
            p.device_id IS NULL
            OR d.id IS NULL
            OR d.deleted_at IS NOT NULL
          )
        """
    ).fetchall()
    print(f"orphan occupied positions: {len(targets)}")
    for row in targets:
        print(
            f"  clear {row['room']}/{row['code']} U{row['u_position']} device={row['device_id']}"
        )
        cur.execute(
            """
            UPDATE rack_position
            SET occupied = 0, device_id = NULL
            WHERE id = ?
            """,
            (row["pos_id"],),
        )

    # Also detach soft-deleted devices that still point at a rack
    dangling = cur.execute(
        """
        SELECT id, hostname, rack_id, u_position
        FROM device
        WHERE deleted_at IS NOT NULL AND rack_id IS NOT NULL
        """
    ).fetchall()
    print(f"soft-deleted devices still linked to rack: {len(dangling)}")
    for row in dangling:
        print(f"  detach {row['hostname']} from rack {row['rack_id']}")
        cur.execute(
            """
            UPDATE device
            SET rack_id = NULL, u_position = NULL, status = 'stock'
            WHERE id = ?
            """,
            (row["id"],),
        )

    conn.commit()

    ab02 = cur.execute(
        """
        SELECT r.code, rm.name AS room,
               (SELECT COUNT(*) FROM rack_position p
                WHERE p.rack_id=r.id AND p.occupied=1 AND p.deleted_at IS NULL) AS occ_u,
               (SELECT COUNT(DISTINCT p.device_id) FROM rack_position p
                WHERE p.rack_id=r.id AND p.occupied=1 AND p.device_id IS NOT NULL
                  AND p.deleted_at IS NULL) AS pos_devs
        FROM rack r
        JOIN room rm ON rm.id = r.room_id
        WHERE r.code = 'AB02' AND rm.name = '303' AND r.deleted_at IS NULL
        """
    ).fetchone()
    print("AB02 after repair:", dict(ab02) if ab02 else None)
    conn.close()


if __name__ == "__main__":
    main()
