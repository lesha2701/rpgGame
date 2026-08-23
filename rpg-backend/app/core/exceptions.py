from fastapi import Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    def __init__(self, code: str, message: str, status_code: int = 400, details: dict | None = None):
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(message)


class NotFoundError(AppError):
    def __init__(self, message: str = "Not found", details: dict | None = None):
        super().__init__("not_found", message, status.HTTP_404_NOT_FOUND, details)


class ForbiddenError(AppError):
    def __init__(self, message: str = "Forbidden", details: dict | None = None):
        super().__init__("forbidden", message, status.HTTP_403_FORBIDDEN, details)


class UnauthorizedError(AppError):
    def __init__(self, message: str = "Unauthorized", details: dict | None = None):
        super().__init__("unauthorized", message, status.HTTP_401_UNAUTHORIZED, details)


class ConflictError(AppError):
    def __init__(self, message: str = "Conflict", details: dict | None = None):
        super().__init__("conflict", message, status.HTTP_409_CONFLICT, details)


class InsufficientResourcesError(AppError):
    """Skill-point budget (Stage 3) — never confuse with InsufficientBalanceError (coins)."""

    def __init__(self, message: str = "Insufficient resources", details: dict | None = None):
        super().__init__("insufficient_resources", message, status.HTTP_400_BAD_REQUEST, details)


class InsufficientBalanceError(AppError):
    """Coins (Stage 5) — ported from the football app's exception of the
    same name. A distinct code from insufficient_resources so a client can
    tell "not enough skill points" apart from "not enough coins"."""

    def __init__(self, message: str = "Insufficient balance", details: dict | None = None):
        super().__init__("insufficient_balance", message, status.HTTP_400_BAD_REQUEST, details)


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def register_exception_handlers(app):
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(status_code=exc.status_code, content=_error_body(exc.code, exc.message, exc.details))

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError):
        # jsonable_encoder, not raw exc.errors(): a field_validator that
        # raises ValueError (see schemas.character.CreateHeroRequest) puts
        # that exception object itself in each error's "ctx", which plain
        # json.dumps (what JSONResponse uses) can't serialize.
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content=_error_body("validation_error", "Invalid request data", {"errors": jsonable_encoder(exc.errors())}),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("http_error", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def unhandled_error_handler(request: Request, exc: Exception):
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=_error_body("internal_error", "Internal server error"),
        )
