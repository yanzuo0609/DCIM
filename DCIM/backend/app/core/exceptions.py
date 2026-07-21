from typing import Any


class AppError(Exception):
    def __init__(
        self,
        message: str,
        code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        self.message = message
        self.code = code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Resource not found", code: int = 404) -> None:
        super().__init__(message=message, code=code)


class ConflictError(AppError):
    def __init__(
        self,
        message: str = "Resource conflict",
        code: int = 409,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message=message, code=code, details=details)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized", code: int = 401) -> None:
        super().__init__(message=message, code=code)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", code: int = 403) -> None:
        super().__init__(message=message, code=code)


class ValidationError(AppError):
    def __init__(self, message: str = "Validation failed", code: int = 422) -> None:
        super().__init__(message=message, code=code)
