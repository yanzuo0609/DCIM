from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends

from app.core.dependencies import get_auth_service, get_current_user
from app.models.user import User
from app.schemas.auth import LoginRequest, RefreshRequest, TokenResponse, UserProfile
from app.schemas.common import ApiResponse
from app.services.auth import AuthService, to_user_profile

router = APIRouter(prefix="/auth")


@router.post("/login", response_model=ApiResponse[TokenResponse])
async def login(
    payload: LoginRequest,
    service: Annotated[AuthService, Depends(get_auth_service)],
) -> ApiResponse[TokenResponse]:
    data = await service.login(payload)
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
    _: Annotated[User, Depends(get_current_user)],
) -> ApiResponse[dict[str, str]]:
    return ApiResponse(data={"message": "logged out"}, timestamp=datetime.now())
