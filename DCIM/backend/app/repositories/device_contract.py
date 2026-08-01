import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.device import Device, DeviceContract, DeviceModel
from app.repositories.base import BaseRepository


class DeviceContractRepository(BaseRepository[DeviceContract]):
    model = DeviceContract

    async def get_by_contract_no(self, contract_no: str) -> DeviceContract | None:
        stmt = select(DeviceContract).where(
            DeviceContract.contract_no == contract_no,
            DeviceContract.deleted_at.is_(None),
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id_full(self, entity_id: uuid.UUID) -> DeviceContract | None:
        stmt = (
            select(DeviceContract)
            .options(
                selectinload(DeviceContract.device_model).selectinload(DeviceModel.manufacturer),
            )
            .where(DeviceContract.id == entity_id, DeviceContract.deleted_at.is_(None))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_ids_full(self, ids: list[uuid.UUID]) -> list[DeviceContract]:
        if not ids:
            return []
        stmt = (
            select(DeviceContract)
            .options(
                selectinload(DeviceContract.device_model).selectinload(DeviceModel.manufacturer),
            )
            .where(DeviceContract.id.in_(ids), DeviceContract.deleted_at.is_(None))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_linked_devices(self, contract_id: uuid.UUID) -> int:
        stmt = select(func.count()).select_from(Device).where(
            Device.contract_id == contract_id,
            Device.deleted_at.is_(None),
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)

    async def linked_counts(self, contract_ids: list[uuid.UUID]) -> dict[uuid.UUID, int]:
        if not contract_ids:
            return {}
        stmt = (
            select(Device.contract_id, func.count())
            .where(
                Device.contract_id.in_(contract_ids),
                Device.deleted_at.is_(None),
            )
            .group_by(Device.contract_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {cid: int(cnt) for cid, cnt in rows if cid is not None}

    async def list_devices(self, contract_id: uuid.UUID) -> list[Device]:
        stmt = (
            select(Device)
            .options(
                selectinload(Device.model).selectinload(DeviceModel.manufacturer),
                selectinload(Device.device_type),
            )
            .where(Device.contract_id == contract_id, Device.deleted_at.is_(None))
            .order_by(Device.hostname)
        )
        return list((await self.session.execute(stmt)).scalars().all())
