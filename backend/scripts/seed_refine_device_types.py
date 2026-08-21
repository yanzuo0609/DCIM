"""Seed refined device types and reclassify existing network devices."""

from __future__ import annotations

import asyncio
import re

from sqlalchemy import select

from app.core.database import async_session_factory
from app.core.seed import seed_device_types
from app.models.device import Device, DeviceModel, DeviceType


def infer_type_code(text: str) -> str | None:
    raw = (text or "").strip()
    if not raw:
        return None
    lower = raw.lower()
    compact = re.sub(r"[\s_\-/]+", "", lower)
    if re.search(r"安全|防火墙|firewall|waf", lower):
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
    if "万兆" in raw or re.search(r"10g|10ge|10gb|tengig|ten_gigabit", compact):
        return "switch_10g"
    if "千兆" in raw or re.search(r"千兆|1ge|gigabit", lower):
        return "switch_1g"
    return None


async def main() -> None:
    async with async_session_factory() as session:
        await seed_device_types(session)
        rows = (
            await session.execute(
                select(DeviceType.code, DeviceType.name)
                .where(DeviceType.deleted_at.is_(None))
                .order_by(DeviceType.code)
            )
        ).all()
        print("types:", rows)

        type_by_code = {
            code: tid
            for tid, code in (
                await session.execute(
                    select(DeviceType.id, DeviceType.code).where(
                        DeviceType.deleted_at.is_(None)
                    )
                )
            ).all()
        }
        code_by_id = {tid: code for code, tid in type_by_code.items()}

        devices = (
            await session.execute(select(Device).where(Device.deleted_at.is_(None)))
        ).scalars().all()
        changed = 0
        for device in devices:
            current = code_by_id.get(device.device_type_id) if device.device_type_id else None
            if current and current != "network":
                continue
            model_name = ""
            if device.device_model_id:
                model = await session.get(DeviceModel, device.device_model_id)
                model_name = model.name if model else ""
            hay = f"{device.name or ''} {device.hostname or ''} {model_name}"
            inferred = infer_type_code(hay)
            if not inferred or inferred not in type_by_code:
                continue
            device.device_type_id = type_by_code[inferred]
            changed += 1
        await session.commit()
        print("reclassified:", changed)


if __name__ == "__main__":
    asyncio.run(main())
