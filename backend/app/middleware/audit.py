"""HTTP middleware that records mutating API calls into audit_log.

Uses pure ASGI (not BaseHTTPMiddleware) so the request DB session commits and
releases SQLite locks *before* audit writes — avoiding “database is locked”
waits that exceed the frontend 30s timeout.
"""

from __future__ import annotations

import logging
import re
import uuid
from starlette.types import ASGIApp, Message, Receive, Scope, Send

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


def _client_ip(scope: Scope) -> str | None:
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    forwarded = headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip() or None
    client = scope.get("client")
    if client:
        return client[0]
    return None


def _parse_identity(scope: Scope) -> tuple[uuid.UUID | None, str | None]:
    headers = {k.decode("latin-1").lower(): v.decode("latin-1") for k, v in scope.get("headers", [])}
    auth = headers.get("authorization") or ""
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


def _should_audit(method: str, path: str) -> bool:
    if method == "OPTIONS" or method not in _MUTATING:
        return False
    if any(path.startswith(p) for p in _SKIP_PREFIXES):
        return False
    if path in _SKIP_PATHS or path.startswith("/api/v1/svg/"):
        return False
    return True


async def _write_audit(
    *,
    method: str,
    path: str,
    status_code: int,
    user_id: uuid.UUID | None,
    username: str | None,
    ip_address: str | None,
) -> None:
    action, resource, resource_id = _resource_action(method, path)
    detail = f"{method} {path} -> {status_code}"
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
            status_code=status_code,
            detail=detail,
            ip_address=ip_address,
        )
        await session.commit()


class AuditLogMiddleware:
    """Pure ASGI middleware — audit runs only after the inner app finishes."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        method = str(scope.get("method") or "").upper()
        path = scope.get("path") or ""
        audit = _should_audit(method, path)
        status_code = 500
        user_id: uuid.UUID | None = None
        username: str | None = None
        ip_address: str | None = None

        if audit:
            user_id, username = _parse_identity(scope)
            ip_address = _client_ip(scope)

        async def send_wrapper(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message.get("status") or 500)
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            if not audit:
                return
            try:
                await _write_audit(
                    method=method,
                    path=path,
                    status_code=status_code,
                    user_id=user_id,
                    username=username,
                    ip_address=ip_address,
                )
            except Exception:  # noqa: BLE001
                logger.exception("Failed to write audit log for %s %s", method, path)
