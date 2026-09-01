"""Safe error handling: never leak internals to the client."""
import logging

from fastapi import Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

logger = logging.getLogger("medsupply")


async def integrity_error_handler(request: Request, exc: IntegrityError):
    # Full detail to the server log, generic message to the client.
    logger.warning("IntegrityError on %s: %s", request.url.path, exc)
    return JSONResponse(
        status_code=status.HTTP_409_CONFLICT,
        content={"detail": "Operation violates a database constraint"},
    )


async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
    logger.error("DB error on %s: %s", request.url.path, exc, exc_info=True)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "A database error occurred"},
    )
