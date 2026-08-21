"""Refine device types: split 1G/10G switches

Revision ID: 0044
Revises: 0043
Create Date: 2026-08-21
"""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "0044_device_type_switch_split"
down_revision: Union[str, None] = "0043_warehouse_asset_quantity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

NEW_TYPES: list[tuple[str, str, str]] = [
    ("switch_1g", "千兆交换机", "接入层千兆交换机（与万兆分属不同类型）"),
    ("switch_10g", "万兆交换机", "接入层万兆交换机（与千兆分属不同类型）"),
    ("switch_agg", "汇聚交换机", "汇聚层交换机"),
    ("switch_core", "核心交换机", "核心层交换机"),
    ("router", "路由器", "路由器/网关"),
]


def _infer_type_code(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    compact = re.sub(r"[\s_\-/]+", "", lower)

    if re.search(r"安全|防火墙|firewall|waf|ids|ips|vpn", lower):
        return "security"
    if re.search(r"存储|storage|san|nas", lower):
        return "storage"
    if re.search(r"服务器|server|compute|host", lower) and not re.search(
        r"交换|switch", lower
    ):
        return "compute"
    if "核心" in raw and re.search(r"交换|switch", lower):
        return "switch_core"
    if "汇聚" in raw and re.search(r"交换|switch", lower):
        return "switch_agg"
    if re.search(r"路由|router", lower):
        return "router"
    if re.search(r"万兆|10g|10ge|10gb|tengig|ten_gigabit|ten-gigabit", compact) or "万兆" in raw:
        return "switch_10g"
    if re.search(r"千兆|1ge|gigabit", lower) or "千兆" in raw:
        # 避免纯数字 1gxx 误伤；名称含千兆优先
        return "switch_1g"
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "device_type" not in tables:
        return

    now = datetime.now(timezone.utc)
    type_t = sa.table(
        "device_type",
        sa.column("id", sa.Uuid()),
        sa.column("code", sa.String()),
        sa.column("name", sa.String()),
        sa.column("is_system", sa.Boolean()),
        sa.column("description", sa.Text()),
        sa.column("created_at", sa.DateTime(timezone=True)),
        sa.column("updated_at", sa.DateTime(timezone=True)),
        sa.column("version", sa.Integer()),
        sa.column("deleted_at", sa.DateTime(timezone=True)),
    )

    existing = {
        row[0]: row[1]
        for row in bind.execute(
            sa.text("SELECT code, id FROM device_type WHERE deleted_at IS NULL")
        ).fetchall()
    }

    for code, name, description in NEW_TYPES:
        if code in existing:
            continue
        new_id = uuid.uuid4()
        bind.execute(
            type_t.insert().values(
                id=new_id,
                code=code,
                name=name,
                is_system=True,
                description=description,
                created_at=now,
                updated_at=now,
                version=1,
                deleted_at=None,
            )
        )
        existing[code] = new_id

    # 更新通用 network 说明
    if "network" in existing:
        bind.execute(
            sa.text(
                "UPDATE device_type SET name = :name, description = :desc, "
                "updated_at = :now WHERE code = 'network' AND deleted_at IS NULL"
            ),
            {
                "name": "网络（通用）",
                "desc": "未细分的网络设备；新建设备请选用千兆/万兆等具体类型",
                "now": now,
            },
        )

    if "device" not in tables:
        return

    # 将仍挂在 network（或名称可推断）的设备细分到千兆/万兆等
    rows = bind.execute(
        sa.text(
            """
            SELECT d.id, d.name, d.hostname, d.device_type_id, t.code AS type_code,
                   m.name AS model_name
            FROM device d
            LEFT JOIN device_type t ON t.id = d.device_type_id
            LEFT JOIN device_model m ON m.id = d.device_model_id
            WHERE d.deleted_at IS NULL
            """
        )
    ).fetchall()

    for row in rows:
        device_id, name, hostname, type_id, type_code, model_name = row
        # 已是细分类型则跳过
        if type_code in {
            "switch_1g",
            "switch_10g",
            "switch_agg",
            "switch_core",
            "router",
            "compute",
            "storage",
            "security",
        }:
            continue
        hay = " ".join(str(x or "") for x in (name, hostname, model_name))
        inferred = _infer_type_code(hay)
        if not inferred or inferred not in existing:
            continue
        # 仅当当前为 network/空，或推断与当前不同且当前为粗粒度 network 时改写
        if type_code and type_code not in (None, "network"):
            continue
        new_type_id = existing[inferred]
        if type_id == new_type_id:
            continue
        bind.execute(
            sa.text(
                "UPDATE device SET device_type_id = :tid, updated_at = :now "
                "WHERE id = :did"
            ),
            {"tid": new_type_id, "now": now, "did": device_id},
        )


def downgrade() -> None:
    # 保留新类型与已迁移数据，不做破坏性回滚
    pass
