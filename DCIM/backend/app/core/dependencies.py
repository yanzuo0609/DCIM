import uuid
from collections.abc import AsyncGenerator, Callable
from typing import Annotated

from fastapi import Depends, Header
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import verify_token
from app.models.user import User
from app.repositories.user import UserRepository
from app.services.audit import AuditService
from app.services.auth import AuthService
from app.services.dashboard import DashboardService
from app.services.device import DeviceService
from app.services.device_contract import DeviceContractService
from app.services.export import DeviceExportService
from app.services.ip_address import IpAddressService
from app.services.infrastructure import (
    BuildingService,
    DataCenterService,
    FloorService,
    RoomService,
)
from app.services.layout import LayoutService
from app.services.network import NetworkDesignService
from app.services.network_interface_export import NetworkInterfaceExportService
from app.services.rack import RackService, RackTemplateService
from app.services.svg import SVGService
from app.services.user_mgmt import RoleManagementService, UserManagementService

security_scheme = HTTPBearer(auto_error=False)


async def get_auth_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuthService:
    return AuthService(session)


async def get_datacenter_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DataCenterService:
    return DataCenterService(session)


async def get_building_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> BuildingService:
    return BuildingService(session)


async def get_floor_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> FloorService:
    return FloorService(session)


async def get_room_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RoomService:
    return RoomService(session)


async def get_rack_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RackService:
    return RackService(session)


async def get_rack_template_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RackTemplateService:
    return RackTemplateService(session)


async def get_device_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceService:
    return DeviceService(session)


async def get_device_contract_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceContractService:
    return DeviceContractService(session)


async def get_ip_address_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> IpAddressService:
    return IpAddressService(session)


async def get_network_design_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NetworkDesignService:
    return NetworkDesignService(session)


async def get_network_interface_export_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> NetworkInterfaceExportService:
    return NetworkInterfaceExportService(session)


async def get_layout_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> LayoutService:
    return LayoutService(session)


async def get_dashboard_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DashboardService:
    return DashboardService(session)


async def get_svg_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> SVGService:
    return SVGService(session)


async def get_audit_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> AuditService:
    return AuditService(session)


async def get_device_export_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> DeviceExportService:
    return DeviceExportService(session)


async def get_user_mgmt_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserManagementService:
    return UserManagementService(session)


async def get_role_mgmt_service(
    session: Annotated[AsyncSession, Depends(get_db)],
) -> RoleManagementService:
    return RoleManagementService(session)


async def get_current_user(
    session: Annotated[AsyncSession, Depends(get_db)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security_scheme)],
) -> User:
    if credentials is None:
        raise UnauthorizedError("Missing authentication token")

    try:
        payload = verify_token(credentials.credentials, token_type="access")
    except ValueError as exc:
        raise UnauthorizedError("Invalid or expired token") from exc

    user_id = uuid.UUID(payload["sub"])
    user = await UserRepository(session).get_with_roles(user_id)
    if not user:
        raise UnauthorizedError("User not found")
    return user


def require_permissions(*required: str) -> Callable:
    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        user_permissions: set[str] = set()
        for role in user.roles:
            for permission in role.permissions:
                user_permissions.add(permission.code)

        if "admin:*" in user_permissions:
            return user

        missing = [perm for perm in required if perm not in user_permissions]
        if missing:
            raise ForbiddenError(f"Missing permissions: {', '.join(missing)}")
        return user

    return checker


def require_any_permission(*required: str) -> Callable:
    """User needs at least one of the listed permissions (or admin:*)."""

    async def checker(user: Annotated[User, Depends(get_current_user)]) -> User:
        user_permissions: set[str] = set()
        for role in user.roles:
            for permission in role.permissions:
                user_permissions.add(permission.code)

        if "admin:*" in user_permissions:
            return user
        if any(perm in user_permissions for perm in required):
            return user
        raise ForbiddenError(f"Missing permissions (need one of): {', '.join(required)}")

    return checker
