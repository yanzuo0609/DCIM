from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=50)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RefreshRequest(BaseModel):
    refresh_token: str


class RoleBrief(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    code: str
    name: str


class UserProfile(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    email: EmailStr
    full_name: str | None
    status: str
    roles: list[RoleBrief]
    permissions: list[str]
    created_at: datetime
