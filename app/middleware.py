import time
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from .logger import logger


class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = (time.time() - start_time) * 1000
        logger.info(
            "%s - %s %s - %d - %.3fms",
            request.client[0],
            request.method,
            request.url.path,
            response.status_code,
            process_time,
        )
        return response
