import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import Depends, FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import get_dynamo_service, router as notifications_router
from app.config import get_settings
from app.consumer.worker import RabbitMqNotificationWorker
from app.services.dynamodb_service import DynamoDbService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("studium.notifications")

settings = get_settings()
dynamo_service = DynamoDbService(settings)
worker = RabbitMqNotificationWorker(settings, dynamo_service=dynamo_service)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Manages application lifecycle: DynamoDB table verification & background RabbitMQ consumer."""
    logger.info("Initializing Studium-Notifications service...")

    # 1. Ensure DynamoDB table exists
    try:
        dynamo_service.ensure_table_exists()
    except Exception as e:
        logger.warning(
            f"Could not verify or provision DynamoDB table on startup: {e}. "
            "Continuing startup (will retry on incoming requests)."
        )

    # 2. Start RabbitMQ consumer worker
    try:
        await worker.start()
    except Exception as e:
        logger.warning(f"Could not start RabbitMQ background worker on startup: {e}. Continuing startup.")

    yield

    # Shutdown
    logger.info("Shutting down Studium-Notifications service...")
    await worker.stop()
    logger.info("Studium-Notifications shutdown complete.")


app = FastAPI(
    title="Studium Notifications Microservice",
    description="Event-driven institutional notification feed and email alert worker backed by Amazon DynamoDB.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(notifications_router)


@app.get("/health", tags=["Health"], status_code=status.HTTP_200_OK)
def health_check(
    dynamo: DynamoDbService = Depends(get_dynamo_service),
) -> JSONResponse:
    """Kubernetes liveness and readiness probe endpoint."""
    dynamo_healthy = dynamo.ping()
    worker_running = worker.running

    is_healthy = dynamo_healthy or settings.environment in ("Development", "Testing")

    return JSONResponse(
        status_code=status.HTTP_200_OK if is_healthy else status.HTTP_503_SERVICE_UNAVAILABLE,
        content={
            "status": "Healthy" if is_healthy else "Degraded",
            "service": "Studium-Notifications",
            "environment": settings.environment,
            "dynamodb": "Connected" if dynamo_healthy else "Disconnected",
            "sqs_worker": "Running" if worker_running else "Stopped",
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
