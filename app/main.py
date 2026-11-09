import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import get_dynamo_service, router as notifications_router
from app.config import get_settings
from app.services.dynamodb_service import DynamoDbService

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("studium.notifications")

settings = get_settings()
dynamo_service = get_dynamo_service()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle and DynamoDB table verification."""
    logger.info("Initializing Studium-Notifications service...")
    try:
        dynamo_service.ensure_table_exists()
    except Exception as e:
        logger.warning(f"Could not verify or provision DynamoDB table on startup: {e}.")

    yield

    logger.info("Studium-Notifications shutdown complete.")


app = FastAPI(
    title="Studium Notifications Microservice",
    description="Synchronous institutional notification feed and email alert API backed by Amazon DynamoDB.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

is_wildcard = not settings.cors_allowed_origins or "*" in settings.cors_allowed_origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if is_wildcard else settings.cors_allowed_origins,
    allow_credentials=not is_wildcard,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(notifications_router)


@app.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
def liveness_check() -> JSONResponse:
    """Kubernetes liveness probe endpoint."""
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "status": "Healthy",
            "service": "Studium-Notifications",
            "environment": settings.environment,
        },
    )


@app.get("/health/ready", tags=["Health"], status_code=status.HTTP_200_OK)
def readiness_check(
    dynamo: DynamoDbService = Depends(get_dynamo_service),
) -> JSONResponse:
    """Kubernetes readiness probe endpoint verifying DynamoDB connectivity."""
    dynamo_healthy = dynamo.ping()
    is_healthy = dynamo_healthy or settings.environment in ("Development", "Testing")

    return JSONResponse(
        status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "Healthy" if is_healthy else "Degraded",
            "service": "Studium-Notifications",
            "environment": settings.environment,
            "dynamodb": "Connected" if dynamo_healthy else "Disconnected",
        },
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.environment == "Development",
    )
