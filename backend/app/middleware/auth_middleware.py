"""
Authentication middleware for protecting API routes.
Validates JWT tokens and enforces face verification status.
"""

import logging
from typing import Optional

from fastapi import Request, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware

from app.services.auth_service import AuthService

logger = logging.getLogger(__name__)

# HTTP Bearer security scheme
security = HTTPBearer()


async def get_current_user(
    credentials: HTTPAuthorizationCredentials,
) -> dict:
    """
    Validate JWT token and return the decoded payload.

    Args:
        credentials: Bearer token credentials.

    Returns:
        Decoded JWT payload with user info.

    Raises:
        HTTPException: If token is invalid or expired.
    """
    token = credentials.credentials
    payload = AuthService.decode_token(token)

    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return payload


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Simple in-memory rate limiting middleware.
    Tracks requests per IP within a time window.

    For production, use Redis-backed rate limiting (e.g., slowapi).
    """

    def __init__(self, app, max_requests: int = 100, window_seconds: int = 60):
        super().__init__(app)
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self._requests: dict = {}  # {ip: [(timestamp, count)]}

    async def dispatch(self, request: Request, call_next):
        import time

        client_ip = request.client.host if request.client else "unknown"
        current_time = time.time()

        # Clean up old entries
        if client_ip in self._requests:
            self._requests[client_ip] = [
                (ts, count)
                for ts, count in self._requests[client_ip]
                if current_time - ts < self.window_seconds
            ]
        else:
            self._requests[client_ip] = []

        # Count requests in current window
        total = sum(count for _, count in self._requests[client_ip])

        if total >= self.max_requests:
            logger.warning(f"Rate limit exceeded for IP: {client_ip}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many requests. Please try again later.",
            )

        # Record this request
        self._requests[client_ip].append((current_time, 1))

        response = await call_next(request)
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add security headers to all responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)

        # Security headers
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = (
            "max-age=31536000; includeSubDomains"
        )
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate"
        response.headers["Pragma"] = "no-cache"

        return response
