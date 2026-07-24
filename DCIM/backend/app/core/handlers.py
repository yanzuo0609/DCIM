from datetime import datetime

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.exceptions import AppError, ConflictError, ForbiddenError, NotFoundError, UnauthorizedError, ValidationError
from app.schemas.common import ErrorResponse

BUSINESS_HTTP_STATUS = {
    10001: 404,
    10002: 409,
    10003: 409,
    10004: 422,
    10005: 422,
}


def _http_status(exc: AppError) -> int:
    if exc.code in BUSINESS_HTTP_STATUS:
        return BUSINESS_HTTP_STATUS[exc.code]
    if isinstance(exc, UnauthorizedError):
        return 401
    if isinstance(exc, ForbiddenError):
        return 403
    if isinstance(exc, NotFoundError):
        return 404
    if isinstance(exc, ConflictError):
        return 409
    if isinstance(exc, ValidationError):
        return 422
    if 400 <= exc.code < 600:
        return exc.code
    return 400


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=_http_status(exc),
            content=ErrorResponse(
                code=exc.code,
                message=exc.message,
                details=exc.details,
                timestamp=datetime.now(),
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        # 便于排查设备定义保存 422
        try:
            print("[RequestValidationError]", exc.errors())
        except Exception:
            print("[RequestValidationError]", str(exc))
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                code=422,
                message="Validation failed",
                details={"errors": exc.errors()},
                timestamp=datetime.now(),
            ).model_dump(mode="json"),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(_: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code=500,
                message="Internal server error",
                details={"detail": str(exc)},
                timestamp=datetime.now(),
            ).model_dump(mode="json"),
        )
