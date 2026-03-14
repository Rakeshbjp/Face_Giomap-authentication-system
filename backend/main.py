"""
Face Auth API — Main Application Entry Point

Production-ready FastAPI application with:
- MongoDB async connection management
- CORS configuration
- Rate limiting middleware
- Security headers
- Structured logging
- Modular route registration
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config.settings import get_settings
from app.config.database import MongoDB
from app.routes.auth_routes import router as auth_router
from app.middleware.auth_middleware import RateLimitMiddleware, SecurityHeadersMiddleware
from app.utils.logging_config import setup_logging

# Initialize logging
setup_logging()
logger = logging.getLogger(__name__)
settings = get_settings()


# ──────────────────────────────────────────────
#  Application Lifespan (startup / shutdown)
# ──────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application startup and shutdown events."""
    # Startup
    logger.info(f"Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    await MongoDB.connect()
    await MongoDB.create_indexes()
    logger.info("Application started successfully")

    yield  # Application is running

    # Shutdown
    logger.info("Shutting down application...")
    await MongoDB.disconnect()
    logger.info("Application shutdown complete")


# ──────────────────────────────────────────────
#  Create FastAPI Application
# ──────────────────────────────────────────────

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Production-ready Face Recognition Authentication API",
    docs_url="/docs" if settings.DEBUG else None,       # Disable Swagger in production
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan,
)


# ──────────────────────────────────────────────
#  Middleware Stack (order matters — outermost first)
# ──────────────────────────────────────────────

# Security headers on every response
app.add_middleware(SecurityHeadersMiddleware)

# Rate limiting
app.add_middleware(
    RateLimitMiddleware,
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW_SECONDS,
)

# CORS
origins = [origin.strip() for origin in settings.CORS_ORIGINS.split(",")]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# ──────────────────────────────────────────────
#  Register Routes
# ──────────────────────────────────────────────

app.include_router(auth_router)


# ──────────────────────────────────────────────
#  Root Endpoint
# ──────────────────────────────────────────────

@app.get("/")
async def root():
    """Root endpoint — basic service info."""
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "running",
    }


# ──────────────────────────────────────────────
#  Entry Point for `python main.py`
# ──────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower(),
        workers=1,  # Use 1 for development; scale with Gunicorn in production
    )
