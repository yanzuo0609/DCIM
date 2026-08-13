import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.network_model_design import (
    NetworkDesignModel,
    NetworkModelFolder,
    NetworkWiringRule,
)
from app.repositories.base import BaseRepository


class NetworkModelFolderRepository(BaseRepository[NetworkModelFolder]):
    model = NetworkModelFolder

    async def list_all(self) -> list[NetworkModelFolder]:
        stmt = (
            select(NetworkModelFolder)
            .where(NetworkModelFolder.deleted_at.is_(None))
            .order_by(NetworkModelFolder.sort_order.asc(), NetworkModelFolder.name.asc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def count_models(self, folder_id: uuid.UUID) -> int:
        stmt = select(func.count()).where(
            NetworkDesignModel.folder_id == folder_id,
            NetworkDesignModel.deleted_at.is_(None),
        )
        return int((await self.session.execute(stmt)).scalar_one() or 0)


class NetworkDesignModelRepository(BaseRepository[NetworkDesignModel]):
    model = NetworkDesignModel

    async def get_by_code(self, code: str) -> NetworkDesignModel | None:
        stmt = select(NetworkDesignModel).where(
            NetworkDesignModel.code == code,
            NetworkDesignModel.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_folder(self, folder_id: uuid.UUID | None = None) -> list[NetworkDesignModel]:
        stmt = select(NetworkDesignModel).where(NetworkDesignModel.deleted_at.is_(None))
        if folder_id:
            stmt = stmt.where(NetworkDesignModel.folder_id == folder_id)
        stmt = stmt.order_by(NetworkDesignModel.updated_at.desc())
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class NetworkWiringRuleRepository(BaseRepository[NetworkWiringRule]):
    model = NetworkWiringRule

    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)

    async def list_by_topology(self, topology_id: uuid.UUID) -> list[NetworkWiringRule]:
        stmt = (
            select(NetworkWiringRule)
            .where(
                NetworkWiringRule.topology_id == topology_id,
                NetworkWiringRule.deleted_at.is_(None),
            )
            .order_by(NetworkWiringRule.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_by_project(self, project_id: uuid.UUID) -> list[NetworkWiringRule]:
        stmt = (
            select(NetworkWiringRule)
            .where(
                NetworkWiringRule.project_id == project_id,
                NetworkWiringRule.deleted_at.is_(None),
            )
            .order_by(NetworkWiringRule.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_all(self) -> list[NetworkWiringRule]:
        stmt = (
            select(NetworkWiringRule)
            .where(NetworkWiringRule.deleted_at.is_(None))
            .order_by(NetworkWiringRule.updated_at.desc())
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
