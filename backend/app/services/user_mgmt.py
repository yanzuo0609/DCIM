import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.core.security import hash_password
from app.models.user import Permission, Role, User, UserStatus
from app.repositories.user import PermissionRepository, RoleRepository, UserRepository
from app.schemas.common import PaginationMeta, PaginationParams
from app.schemas.user_mgmt import (
    PermissionResponse,
    RoleBrief,
    RoleCreate,
    RoleResponse,
    RoleUpdate,
    UserCreate,
    UserResponse,
    UserUpdate,
)


def _to_user_response(user: User) -> UserResponse:
    return UserResponse(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        status=user.status.value if isinstance(user.status, UserStatus) else user.status,
        roles=[RoleBrief(id=str(r.id), code=r.code, name=r.name) for r in user.roles],
        created_at=user.created_at,
        updated_at=user.updated_at,
    )


def _to_role_response(role: Role) -> RoleResponse:
    return RoleResponse(
        id=str(role.id),
        code=role.code,
        name=role.name,
        description=role.description,
        permissions=[
            PermissionResponse(
                id=str(p.id), code=p.code, name=p.name, description=p.description
            )
            for p in role.permissions
        ],
        created_at=role.created_at,
        updated_at=role.updated_at,
    )


class UserManagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.user_repo = UserRepository(session)
        self.role_repo = RoleRepository(session)

    async def list_users(
        self, params: PaginationParams
    ) -> tuple[list[UserResponse], PaginationMeta]:
        items, total = await self.user_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["username", "email", "full_name"],
        )
        enriched = []
        for item in items:
            user = await self.user_repo.get_with_roles(item.id)
            if user:
                enriched.append(_to_user_response(user))
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return enriched, pagination

    async def get_user(self, user_id: uuid.UUID) -> UserResponse:
        user = await self.user_repo.get_with_roles(user_id)
        if not user:
            raise NotFoundError("User not found")
        return _to_user_response(user)

    async def create_user(
        self, payload: UserCreate, user_id: uuid.UUID | None = None
    ) -> UserResponse:
        if await self.user_repo.get_by_username(payload.username):
            raise ConflictError("Username already exists")
        if await self.user_repo.get_by_email(str(payload.email)):
            raise ConflictError("Email already exists")

        role_ids = [uuid.UUID(rid) for rid in payload.role_ids]
        for rid in role_ids:
            if not await self.role_repo.get_by_id(rid):
                raise NotFoundError(f"Role not found: {rid}")

        user = User(
            username=payload.username,
            email=str(payload.email),
            password_hash=hash_password(payload.password),
            full_name=payload.full_name,
            status=UserStatus(payload.status),
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.user_repo.create(user)
        if role_ids:
            await self.user_repo.set_roles(created, role_ids)
            self.session.expire(created, ["roles"])
        result = await self.user_repo.get_with_roles(created.id)
        assert result is not None
        return _to_user_response(result)

    async def update_user(
        self,
        target_id: uuid.UUID,
        payload: UserUpdate,
        actor_id: uuid.UUID | None = None,
    ) -> UserResponse:
        user = await self.user_repo.get_with_roles(target_id)
        if not user:
            raise NotFoundError("User not found")

        if payload.email and str(payload.email) != user.email:
            if await self.user_repo.get_by_email(str(payload.email)):
                raise ConflictError("Email already exists")
            user.email = str(payload.email)
        if payload.full_name is not None:
            user.full_name = payload.full_name
        if payload.status is not None:
            user.status = UserStatus(payload.status)
        if payload.password:
            user.password_hash = hash_password(payload.password)
        if payload.role_ids is not None:
            role_ids = [uuid.UUID(rid) for rid in payload.role_ids]
            await self.user_repo.set_roles(user, role_ids)
            self.session.expire(user, ["roles"])

        user.updated_by = actor_id
        user.version += 1
        await self.session.flush()
        updated = await self.user_repo.get_with_roles(target_id)
        assert updated is not None
        return _to_user_response(updated)

    async def delete_user(self, target_id: uuid.UUID, actor_id: uuid.UUID | None = None) -> None:
        user = await self.user_repo.get_by_id(target_id)
        if not user:
            raise NotFoundError("User not found")
        if user.username == "admin":
            raise ValidationError("Cannot delete default admin user")
        await self.user_repo.soft_delete(user, deleted_by=actor_id)


class RoleManagementService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.role_repo = RoleRepository(session)
        self.perm_repo = PermissionRepository(session)

    async def list_roles(
        self, params: PaginationParams
    ) -> tuple[list[RoleResponse], PaginationMeta]:
        items, total = await self.role_repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            search_fields=["code", "name"],
        )
        enriched = []
        for item in items:
            role = await self.role_repo.get_with_permissions(item.id)
            if role:
                enriched.append(_to_role_response(role))
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return enriched, pagination

    async def list_permissions(self) -> list[PermissionResponse]:
        perms = await self.perm_repo.list_all()
        return [
            PermissionResponse(id=str(p.id), code=p.code, name=p.name, description=p.description)
            for p in perms
        ]

    async def create_role(
        self, payload: RoleCreate, user_id: uuid.UUID | None = None
    ) -> RoleResponse:
        if await self.role_repo.get_by_code(payload.code):
            raise ConflictError("Role code already exists")
        role = Role(
            code=payload.code,
            name=payload.name,
            description=payload.description,
            created_by=user_id,
            updated_by=user_id,
        )
        created = await self.role_repo.create(role)
        if payload.permission_ids:
            perm_ids = [uuid.UUID(pid) for pid in payload.permission_ids]
            await self.role_repo.set_permissions(created, perm_ids)
            self.session.expire(created, ["permissions"])
        result = await self.role_repo.get_with_permissions(created.id)
        assert result is not None
        return _to_role_response(result)

    async def update_role(
        self,
        role_id: uuid.UUID,
        payload: RoleUpdate,
        user_id: uuid.UUID | None = None,
    ) -> RoleResponse:
        role = await self.role_repo.get_with_permissions(role_id)
        if not role:
            raise NotFoundError("Role not found")
        if role.code == "admin" and payload.permission_ids is not None:
            raise ValidationError("Cannot modify admin role permissions via API")

        if payload.name is not None:
            role.name = payload.name
        if payload.description is not None:
            role.description = payload.description
        if payload.permission_ids is not None:
            perm_ids = [uuid.UUID(pid) for pid in payload.permission_ids]
            await self.role_repo.set_permissions(role, perm_ids)
            self.session.expire(role, ["permissions"])

        role.updated_by = user_id
        role.version += 1
        await self.session.flush()
        updated = await self.role_repo.get_with_permissions(role_id)
        assert updated is not None
        return _to_role_response(updated)

    async def delete_role(self, role_id: uuid.UUID, user_id: uuid.UUID | None = None) -> None:
        role = await self.role_repo.get_by_id(role_id)
        if not role:
            raise NotFoundError("Role not found")
        if role.code == "admin":
            raise ValidationError("Cannot delete admin role")
        await self.role_repo.soft_delete(role, deleted_by=user_id)
