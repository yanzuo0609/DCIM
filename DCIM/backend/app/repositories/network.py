import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.network import NetworkLink, NetworkNode, NetworkProject, NetworkTopology
from app.repositories.base import BaseRepository


class NetworkProjectRepository(BaseRepository[NetworkProject]):
    model = NetworkProject

    async def get_by_code(self, code: str) -> NetworkProject | None:
        stmt = select(NetworkProject).where(
            NetworkProject.code == code,
            NetworkProject.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_primary_topology(self, project_id: uuid.UUID) -> NetworkTopology | None:
        stmt = (
            select(NetworkTopology)
            .where(
                NetworkTopology.project_id == project_id,
                NetworkTopology.deleted_at.is_(None),
            )
            .order_by(NetworkTopology.created_at.asc())
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()


class NetworkTopologyRepository(BaseRepository[NetworkTopology]):
    model = NetworkTopology

    async def get_with_canvas(self, topology_id: uuid.UUID) -> NetworkTopology | None:
        stmt = (
            select(NetworkTopology)
            .where(NetworkTopology.id == topology_id, NetworkTopology.deleted_at.is_(None))
            .options(
                selectinload(NetworkTopology.nodes),
                selectinload(NetworkTopology.links),
            )
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def list_by_project(self, project_id: uuid.UUID) -> list[NetworkTopology]:
        stmt = select(NetworkTopology).where(
            NetworkTopology.project_id == project_id,
            NetworkTopology.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class NetworkNodeRepository(BaseRepository[NetworkNode]):
    model = NetworkNode

    async def list_by_topology(self, topology_id: uuid.UUID) -> list[NetworkNode]:
        stmt = select(NetworkNode).where(
            NetworkNode.topology_id == topology_id,
            NetworkNode.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())


class NetworkLinkRepository(BaseRepository[NetworkLink]):
    model = NetworkLink

    async def list_by_topology(self, topology_id: uuid.UUID) -> list[NetworkLink]:
        stmt = select(NetworkLink).where(
            NetworkLink.topology_id == topology_id,
            NetworkLink.deleted_at.is_(None),
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
