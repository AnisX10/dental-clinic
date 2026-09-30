"""Central application error type and exception handlers.

Business errors carry a stable machine `code` and an i18n `message_key`.
The frontend translates `message_key` (French/Arabic); the backend never sends
user-facing prose. Technical detail goes to logs only.
"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

logger = logging.getLogger("clinic")


class AppError(Exception):
    def __init__(
        self,
        message_key: str,
        *,
        status_code: int = 400,
        code: str = "error",
        values: dict | None = None,
    ):
        super().__init__(message_key)
        self.message_key = message_key
        self.status_code = status_code
        self.code = code
        self.values = values or {}


def _payload(message_key: str, code: str, values: dict) -> dict:
    return {"error": {"code": code, "message_key": message_key, "values": values}}


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_payload(exc.message_key, exc.code, exc.values),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_handler(request: Request, exc: RequestValidationError):
        field = None
        for err in exc.errors():
            loc = err.get("loc", [])
            if len(loc) >= 2:
                field = str(loc[-1])
                break
        return JSONResponse(
            status_code=422,
            content=_payload("errors.validation", "validation_error", {"field": field} if field else {}),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(request: Request, exc: Exception):
        # Log server-side; never leak internals or medical content to the UI.
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(
            status_code=500,
            content=_payload("errors.internal", "internal_error", {}),
        )
