from datetime import datetime
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

T = TypeVar("T")


class PaginationParams(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=500)
    keyword: str | None = None
    sort: str = "created_at"
    order: str = "desc"


class PaginationMeta(BaseModel):
    page: int
    page_size: int
    total: int
    pages: int


class ApiResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: T | None = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class PaginatedData(BaseModel, Generic[T]):
    items: list[T]
    pagination: PaginationMeta


class PaginatedResponse(BaseModel, Generic[T]):
    code: int = 0
    message: str = "success"
    data: PaginatedData[T]
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class ErrorResponse(BaseModel):
    code: int
    message: str
    details: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=lambda: datetime.now())


class AuditSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
