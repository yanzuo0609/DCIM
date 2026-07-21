import math
import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError, UnauthorizedError
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
    verify_token,
)
from app.models.user import User, UserStatus
from app.repositories.user import UserRepository
from app.schemas.auth import LoginRequest, RoleBrief, TokenResponse, UserProfile


def collect_permissions(user: User) -> list[str]:
    permissions: set[str] = set()
    for role in user.roles:
        for permission in role.permissions:
            permissions.add(permission.code)
    return sorted(permissions)


def to_user_profile(user: User) -> UserProfile:
    return UserProfile(
        id=str(user.id),
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        status=user.status.value,
        roles=[
            RoleBrief(id=str(role.id), code=role.code, name=role.name) for role in user.roles
        ],
        permissions=collect_permissions(user),
        created_at=user.created_at,
    )


class AuthService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = UserRepository(session)
        self.settings = get_settings()

    async def login(self, payload: LoginRequest) -> TokenResponse:
        user = await self.repo.get_by_username(payload.username)
        if not user:
            raise UnauthorizedError("Invalid username or password")

        now = datetime.now(timezone.utc)
        if user.status == UserStatus.LOCKED:
            if user.locked_until and user.locked_until > now:
                raise ForbiddenError("Account is locked")
            user.status = UserStatus.ACTIVE
            user.failed_login_count = 0
            user.locked_until = None

        if not verify_password(payload.password, user.password_hash):
            user.failed_login_count += 1
            if user.failed_login_count >= 5:
                user.status = UserStatus.LOCKED
                user.locked_until = now + timedelta(minutes=15)
            raise UnauthorizedError("Invalid username or password")

        user.failed_login_count = 0
        user.locked_until = None

        permissions = collect_permissions(user)
        extra = {
            "username": user.username,
            "roles": [role.code for role in user.roles],
            "permissions": permissions,
        }
        access_token = create_access_token(str(user.id), extra)
        refresh_token = create_refresh_token(str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )

    async def refresh(self, refresh_token: str) -> TokenResponse:
        try:
            payload = verify_token(refresh_token, token_type="refresh")
        except ValueError as exc:
            raise UnauthorizedError("Invalid refresh token") from exc

        user = await self.repo.get_with_roles(uuid.UUID(payload["sub"]))
        if not user or user.status != UserStatus.ACTIVE:
            raise UnauthorizedError("Invalid refresh token")

        permissions = collect_permissions(user)
        extra = {
            "username": user.username,
            "roles": [role.code for role in user.roles],
            "permissions": permissions,
        }
        access_token = create_access_token(str(user.id), extra)
        new_refresh_token = create_refresh_token(str(user.id))
        return TokenResponse(
            access_token=access_token,
            refresh_token=new_refresh_token,
            expires_in=self.settings.access_token_expire_minutes * 60,
        )

    async def get_profile(self, user_id: uuid.UUID) -> UserProfile:
        user = await self.repo.get_with_roles(user_id)
        if not user:
            raise NotFoundError("User not found")
        return to_user_profile(user)

    @staticmethod
    def hash_password(password: str) -> str:
        return hash_password(password)
