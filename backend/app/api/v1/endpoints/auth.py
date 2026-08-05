from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request

from app.core.database import async_session_factory
from app.core.dependencies import get_auth_service, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserProfile
from app.schemas.common import ApiResponse
from app.services.audit import AuditService
from app.services.auth import AuthService, to_user_profile

router = APIRouter(prefix="/auth")


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None


async def _write_auth_audit(**kwargs) -> None:
    """Write auth audit in an isolated session so failures still persist."""
    async with async_session_factory() as session:
        await AuditService(session).log(**kwargs)
        await session.commit()


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    payload: LoginRequest,
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[TokenResponse]:
    try:
        data = await service.login(payload)
    except Exception:
        await _write_auth_audit(
            user_id=None,
            username=payload.username,
            action="login_failed",
            resource="auth",
            resource_id=None,
            method="POST",
            path="/api/v1/auth/login",
            status_code=401,
            detail=f"login failed for {payload.username}",
            ip_address=_client_ip(request),
        )
        raise
    await _write_auth_audit(
        user_id=None,
        username=payload.username,
        action="login",
        resource="auth",
        resource_id=None,
        method="POST",
        path="/api/v1/auth/login",
        status_code=200,
        detail=f"login success for {payload.username}",
        ip_address=_client_ip(request),
    )
    return ApiResponse(data=data, timestamp=datetime.now())


@router.post("/refresh", response_model=ApiResponse[TokenResponse])
async def refresh_token(
    payload: RefreshRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[TokenResponse]:
    data = await service.refresh(payload.refresh_token)
    return ApiResponse(data=data, timestamp=datetime.now())


@router.get("/profile", response_model=ApiResponse[UserProfile])
async def get_profile(
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[UserProfile]:
    return ApiResponse(data=to_user_profile(current_user), timestamp=datetime.now())


@router.post("/logout", response_model=ApiResponse[dict[str, str]])
async def logout(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict[str, str]]:
    await _write_auth_audit(
        user_id=current_user.id,
        username=current_user.username,
        action="logout",
        resource="auth",
        resource_id=str(current_user.id),
        method="POST",
        path="/api/v1/auth/logout",
        status_code=200,
        detail=f"logout {current_user.username}",
        ip_address=_client_ip(request),
    )
    return ApiResponse(data={"message": "logged out"}, timestamp=datetime.now())
