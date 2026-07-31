import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog
from app.repositories.base import BaseRepository


class AuditLogRepository(BaseRepository[AuditLog]):
    model = AuditLog

    async def create_log(
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
    ) -> AuditLog:
        log = AuditLog(
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
        return await self.create(log)
