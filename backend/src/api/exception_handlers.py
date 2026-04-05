import logging
import re

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("jobtracker")

_CONFLICT_RE = re.compile(
    r"Embedding function conflict:\s*new:\s*(\S+)\s*vs\s*persisted:\s*(\S+)",
    re.IGNORECASE,
)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(ValueError)
    async def handle_value_error(request: Request, exc: ValueError):
        message = str(exc)
        match = _CONFLICT_RE.search(message)
        if not match:
            raise exc
        new_ef, persisted_ef = match.group(1), match.group(2)
        logger.warning(
            "Embedding function conflict: new=%s persisted=%s", new_ef, persisted_ef
        )
        return JSONResponse(
            status_code=409,
            content={
                "error": "embedding_mismatch",
                "message": "Embedding model changed since this collection was built. Reindex required.",
                "new": new_ef,
                "persisted": persisted_ef,
            },
        )
