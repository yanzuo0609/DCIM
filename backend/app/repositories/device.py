import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.device import (
    Device,
    DeviceBmcProfile,
    DeviceCategory,
    DeviceModel,
    DeviceParamProfile,
    DeviceSystemProfile,
    DeviceType,
    Manufacturer,
)
from app.repositories.base import BaseRepository


class ManufacturerRepository(BaseRepository[Manufacturer]):
    model = Manufacturer

    async def get_by_code(self, code: str) -> Manufacturer | None:
        stmt = select(Manufacturer).where(
            Manufacturer.code == code, Manufacturer.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class DeviceCategoryRepository(BaseRepository[DeviceCategory]):
    model = DeviceCategory

    async def get_by_code(self, code: str) -> DeviceCategory | None:
        stmt = select(DeviceCategory).where(
            DeviceCategory.code == code, DeviceCategory.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class DeviceTypeRepository(BaseRepository[DeviceType]):
    model = DeviceType

    async def get_by_code(self, code: str) -> DeviceType | None:
        stmt = select(DeviceType).where(DeviceType.code == code, DeviceType.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count_devices(self, type_id: uuid.UUID) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Device).where(
            Device.device_type_id == type_id,
            Device.deleted_at.is_(None),
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)


class DeviceParamProfileRepository(BaseRepository[DeviceParamProfile]):
    model = DeviceParamProfile

    async def get_by_code(self, code: str) -> DeviceParamProfile | None:
        stmt = select(DeviceParamProfile).where(
            DeviceParamProfile.code == code, DeviceParamProfile.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class DeviceSystemProfileRepository(BaseRepository[DeviceSystemProfile]):
    model = DeviceSystemProfile

    async def get_by_code(self, code: str) -> DeviceSystemProfile | None:
        stmt = select(DeviceSystemProfile).where(
            DeviceSystemProfile.code == code, DeviceSystemProfile.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class DeviceBmcProfileRepository(BaseRepository[DeviceBmcProfile]):
    model = DeviceBmcProfile

    async def get_by_code(self, code: str) -> DeviceBmcProfile | None:
        stmt = select(DeviceBmcProfile).where(
            DeviceBmcProfile.code == code, DeviceBmcProfile.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()


class DeviceModelRepository(BaseRepository[DeviceModel]):
    model = DeviceModel

    async def get_by_code(self, code: str) -> DeviceModel | None:
        stmt = select(DeviceModel).where(
            DeviceModel.code == code, DeviceModel.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_id_with_mfg(self, model_id: uuid.UUID) -> DeviceModel | None:
        stmt = (
            select(DeviceModel)
            .options(selectinload(DeviceModel.manufacturer))
            .where(DeviceModel.id == model_id, DeviceModel.deleted_at.is_(None))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_ids_with_mfg(self, ids: list[uuid.UUID]) -> list[DeviceModel]:
        if not ids:
            return []
        stmt = (
            select(DeviceModel)
            .options(selectinload(DeviceModel.manufacturer))
            .where(DeviceModel.id.in_(ids), DeviceModel.deleted_at.is_(None))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def count_devices(self, model_id: uuid.UUID) -> int:
        from sqlalchemy import func

        stmt = select(func.count()).select_from(Device).where(
            Device.device_model_id == model_id,
            Device.deleted_at.is_(None),
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)


class DeviceRepository(BaseRepository[Device]):
    model = Device

    def _with_relations(self):
        return (
            selectinload(Device.model).selectinload(DeviceModel.manufacturer),
            selectinload(Device.device_type),
            selectinload(Device.param_profile),
            selectinload(Device.system_profile),
            selectinload(Device.bmc_profile),
            selectinload(Device.contract),
            selectinload(Device.ip_addresses),
        )

    def _with_list_relations(self):
        """List view: model/type/IP/contract — skip bulky profile payloads."""
        return (
            selectinload(Device.model).selectinload(DeviceModel.manufacturer),
            selectinload(Device.device_type),
            selectinload(Device.contract),
            selectinload(Device.ip_addresses),
        )

    async def get_by_id_with_model(self, device_id: uuid.UUID) -> Device | None:
        stmt = (
            select(Device)
            .options(*self._with_relations())
            .where(Device.id == device_id, Device.deleted_at.is_(None))
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def list_by_ids_with_relations(self, ids: list[uuid.UUID]) -> list[Device]:
        if not ids:
            return []
        stmt = (
            select(Device)
            .options(*self._with_relations())
            .where(Device.id.in_(ids), Device.deleted_at.is_(None))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_by_ids_for_list(self, ids: list[uuid.UUID]) -> list[Device]:
        if not ids:
            return []
        stmt = (
            select(Device)
            .options(*self._with_list_relations())
            .where(Device.id.in_(ids), Device.deleted_at.is_(None))
        )
        return list((await self.session.execute(stmt)).scalars().all())

    async def list_paginated_by_room(
        self,
        room_id: uuid.UUID,
        *,
        page: int = 1,
        page_size: int = 20,
        keyword: str | None = None,
        sort: str = "created_at",
        order: str = "desc",
        status: str | None = None,
    ) -> tuple[list[Device], int]:
        """List devices in a room via join (avoids large rack_id IN lists)."""
        from sqlalchemy import asc, desc, func, or_

        from app.models.rack import Rack

        filters = [
            Device.deleted_at.is_(None),
            Rack.deleted_at.is_(None),
            Rack.room_id == room_id,
        ]
        if status:
            filters.append(Device.status == status)
        if keyword:
            filters.append(
                or_(
                    Device.hostname.ilike(f"%{keyword}%"),
                    Device.serial_number.ilike(f"%{keyword}%"),
                    Device.name.ilike(f"%{keyword}%"),
                )
            )
        count_stmt = (
            select(func.count())
            .select_from(Device)
            .join(Rack, Device.rack_id == Rack.id)
            .where(*filters)
        )
        total = (await self.session.execute(count_stmt)).scalar_one()
        sort_column = getattr(Device, sort, Device.created_at)
        order_fn = desc if order.lower() == "desc" else asc
        stmt = (
            select(Device)
            .join(Rack, Device.rack_id == Rack.id)
            .where(*filters)
            .order_by(order_fn(sort_column))
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
        return list((await self.session.execute(stmt)).scalars().unique().all()), int(total or 0)

    async def get_by_serial(self, serial_number: str) -> Device | None:
        stmt = select(Device).where(
            Device.serial_number == serial_number, Device.deleted_at.is_(None)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def get_by_hostname(self, hostname: str) -> Device | None:
        stmt = select(Device).where(Device.hostname == hostname, Device.deleted_at.is_(None))
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def count_all(self) -> int:
        stmt = select(Device).where(Device.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return len(list(result.scalars().all()))

    async def list_by_rack(self, rack_id: uuid.UUID) -> list[Device]:
        stmt = (
            select(Device)
            .options(
                selectinload(Device.model),
                selectinload(Device.ip_addresses),
            )
            .where(Device.rack_id == rack_id, Device.deleted_at.is_(None))
            .order_by(Device.u_position)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
