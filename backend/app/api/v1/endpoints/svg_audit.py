import uuid
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response

from app.core.dependencies import get_audit_service, get_svg_service, require_permissions
from app.models.user import User
from app.schemas.common import ApiResponse, PaginatedData, PaginatedResponse, PaginationParams
from app.services.audit import AuditService
from app.services.svg import SVGService

router = APIRouter()


@router.get("/svg/rack/{rack_id}")
async def get_rack_svg(
    rack_id: uuid.UUID,
    service: Annotated[SVGService, Depends(get_svg_service)],
    _: Annotated[User, Depends(require_permissions("rack:view"))],
) -> Response:
    svg = await service.render_rack(rack_id)
    return Response(content=svg, media_type="image/svg+xml")


@router.get("/audit/logs", response_model=PaginatedResponse[dict])
async def list_audit_logs(
    service: Annotated[AuditService, Depends(get_audit_service)],
    _: Annotated[User, Depends(require_permissions("audit:view"))],
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
    keyword: str | None = None,
) -> PaginatedResponse[dict]:
    params = PaginationParams(page=page, page_size=page_size, keyword=keyword)
    items, pagination = await service.list_logs(params)
    return PaginatedResponse(
        data=PaginatedData(items=items, pagination=pagination),
        timestamp=datetime.now(),
    )
