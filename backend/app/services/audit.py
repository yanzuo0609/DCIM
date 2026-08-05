import math
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.repositories.audit import AuditLogRepository
from app.schemas.common import PaginationMeta, PaginationParams


class AuditService:
    def __init__(self, session: AsyncSession) -> None:
        self.repo = AuditLogRepository(session)

    async def list_logs(
        self, params: PaginationParams
    ) -> tuple[list[dict], PaginationMeta]:
        items, total = await self.repo.list_paginated(
            page=params.page,
            page_size=params.page_size,
            keyword=params.keyword,
            sort=params.sort,
            order=params.order,
            search_fields=["action", "resource", "username", "path"],
        )
        pagination = PaginationMeta(
            page=params.page,
            page_size=params.page_size,
            total=total,
            pages=math.ceil(total / params.page_size) if total else 0,
        )
        return [
            {
                "id": str(i.id),
                "user_id": str(i.user_id) if i.user_id else None,
                "username": i.username,
                "action": i.action,
                "resource": i.resource,
                "resource_id": i.resource_id,
                "method": i.method,
                "path": i.path,
                "ip_address": i.ip_address,
                "status_code": i.status_code,
                "detail": i.detail,
                "created_at": i.created_at.isoformat(),
            }
            for i in items
        ], pagination

    async def log(
        self,
        *,
        user_id: uuid.UUID | None,
        username: str | None,
        action: str,
        resource: str,
        resource_id: str | None,
        method: str,
        path: str,
        status_code: int = 200,
        detail: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        await self.repo.create_log(
            user_id=user_id,
            username=username,
            action=action,
            resource=resource,
            resource_id=resource_id,
            method=method,
            path=path,
            status_code=status_code,
            detail=detail,
            ip_address=ip_address,
        )
