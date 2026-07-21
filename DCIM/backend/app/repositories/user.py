import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.user import Permission, Role, User, UserRole
from app.repositories.base import BaseRepository


class UserRepository(BaseRepository[User]):
    model = User

    async def get_by_username(self, username: str) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.roles).selectinload(Role.permissions),
            )
            .where(User.username == username, User.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(User).where(User.email == email, User.deleted_at.is_(None))
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_roles(self, user_id: uuid.UUID) -> User | None:
        stmt = (
            select(User)
            .options(
                selectinload(User.roles).selectinload(Role.permissions),
            )
            .where(User.id == user_id, User.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_roles(self, user: User, role_ids: list[uuid.UUID]) -> None:
        stmt = select(UserRole).where(UserRole.user_id == user.id)
        existing = list((await self.session.execute(stmt)).scalars().all())
        for link in existing:
            await self.session.delete(link)

        for role_id in role_ids:
            self.session.add(UserRole(user_id=user.id, role_id=role_id))
        await self.session.flush()


class RoleRepository(BaseRepository[Role]):
    model = Role

    async def get_by_code(self, code: str) -> Role | None:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.code == code, Role.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_with_permissions(self, role_id: uuid.UUID) -> Role | None:
        stmt = (
            select(Role)
            .options(selectinload(Role.permissions))
            .where(Role.id == role_id, Role.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def set_permissions(self, role: Role, permission_ids: list[uuid.UUID]) -> None:
        from app.models.user import RolePermission

        stmt = select(RolePermission).where(RolePermission.role_id == role.id)
        existing = list((await self.session.execute(stmt)).scalars().all())
        for link in existing:
            await self.session.delete(link)

        for perm_id in permission_ids:
            self.session.add(RolePermission(role_id=role.id, permission_id=perm_id))
        await self.session.flush()


class PermissionRepository(BaseRepository[Permission]):
    model = Permission

    async def list_all(self) -> list[Permission]:
        stmt = select(Permission).where(Permission.deleted_at.is_(None)).order_by(Permission.code)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ids(self, permission_ids: list[uuid.UUID]) -> list[Permission]:
        stmt = select(Permission).where(
            Permission.id.in_(permission_ids), Permission.deleted_at.is_(None)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
