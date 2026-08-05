"""HTTP middleware that records mutating API calls into audit_log."""

from __future__ import annotations

import logging
import re
import uuid
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from app.core.database import async_session_factory
from app.core.security import verify_token
from app.services.audit import AuditService

logger = logging.getLogger(__name__)

_MUTATING = {"POST", "PUT", "PATCH", "DELETE"}
_SKIP_PREFIXES = (
    "/health",
    "/api/v1/docs",
    "/api/v1/redoc",
    "/api/v1/openapi.json",
)
_SKIP_PATHS = {
    "/api/v1/audit/logs",
    "/api/v1/auth/login",
    "/api/v1/auth/logout",
    "/api/v1/auth/refresh",
}
_UUID_RE = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    if request.client:
        return request.client.host
    return None


def _parse_identity(request: Request) -> tuple[uuid.UUID | None, str | None]:
    auth = request.headers.get("authorization") or ""
    if not auth.lower().startswith("bearer "):
        return None, None
    token = auth[7:].strip()
    if not token:
        return None, None
    try:
        payload = verify_token(token, token_type="access")
        user_id = uuid.UUID(str(payload["sub"]))
        username = payload.get("username")
        return user_id, str(username) if username else None
    except Exception:  # noqa: BLE001
        return None, None


def _resource_action(method: str, path: str) -> tuple[str, str, str | None]:
    """Derive (action, resource, resource_id) from method + path."""
    parts = [p for p in path.split("/") if p]
    # expect api/v1/<resource>/...
    if len(parts) >= 2 and parts[0] == "api" and parts[1] == "v1":
        parts = parts[2:]
    if not parts:
        return method.lower(), "system", None

    resource = parts[0]
    resource_id: str | None = None
    rest = parts[1:]

    for seg in rest:
        if _UUID_RE.match(seg) or seg.isdigit():
            resource_id = seg
            break

    action_map = {
        "POST": "create",
        "PUT": "update",
        "PATCH": "update",
        "DELETE": "delete",
    }
    action = action_map.get(method, method.lower())

    # auth specials
    if resource == "auth" and rest:
        if rest[0] == "login":
            return "login", "auth", None
        if rest[0] == "logout":
            return "logout", "auth", None
        if rest[0] == "refresh":
            return "refresh", "auth", None

    # nested actions e.g. /layout/batch-mount
    if rest and not _UUID_RE.match(rest[0]) and not rest[0].isdigit():
        if method == "POST":
            action = rest[0].replace("-", "_")

    return action, resource, resource_id


class AuditLogMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)

        method = request.method.upper()
        path = request.url.path

        if method == "OPTIONS" or method not in _MUTATING:
            return response
        if any(path.startswith(p) for p in _SKIP_PREFIXES):
            return response
        if path in _SKIP_PATHS or path.startswith("/api/v1/svg/"):
            return response

        try:
            user_id, username = _parse_identity(request)
            action, resource, resource_id = _resource_action(method, path)
            # login has no bearer yet — keep username from path only
            detail = f"{method} {path} -> {response.status_code}"
            async with async_session_factory() as session:
                service = AuditService(session)
                await service.log(
                    user_id=user_id,
                    username=username,
                    action=action,
                    resource=resource,
                    resource_id=resource_id,
                    method=method,
                    path=path[:255],
                    status_code=response.status_code,
                    detail=detail,
                    ip_address=_client_ip(request),
                )
                await session.commit()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to write audit log for %s %s", method, path)

        return response
