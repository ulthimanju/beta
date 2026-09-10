from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, get_logger
from app.core.telemetry import setup_telemetry
from app.core.metrics import setup_metrics
from app.api.v1.router import api_v1_router
from app.services.redis_client import close_redis_client
from app.services.queue_client import close_queue_connection

# Initialize structured logging
setup_logging(debug=settings.DEBUG)
logger = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application startup and graceful shutdown lifecycle."""
    logger.info(
        "Starting repoAnalyzer microservice",
        app_name=settings.APP_NAME,
        environment=settings.ENVIRONMENT,
        debug=settings.DEBUG,
    )
    yield
    logger.info("Shutting down repoAnalyzer microservice")
    from app.services.sandbox_manager import sandbox_manager
    await sandbox_manager.close_all()
    await close_redis_client()
    await close_queue_connection()


app = FastAPI(
    title="repoAnalyzer API",
    description="Microservice orchestrating codebase fetching and AI agent architectural analysis",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# OpenTelemetry & Prometheus setup
setup_telemetry(app)
setup_metrics(app)

# Include API Routers
app.include_router(api_v1_router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root metadata endpoint."""
    return {
        "service": settings.APP_NAME,
        "docs": "/docs",
        "health": "/api/v1/health",
        "metrics": "/metrics",
    }
