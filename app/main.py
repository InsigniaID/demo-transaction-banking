from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .core.config import settings
from .database import Base, engine
from .kafka_producer import init_kafka, shutdown_kafka
from .api.v1.api import api_router
from .middleware import performance_monitoring_middleware

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="Banking Transaction Demo API"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Add performance monitoring middleware
app.middleware("http")(performance_monitoring_middleware)


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup."""
    await init_kafka()


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup services on shutdown."""
    await shutdown_kafka()


@app.get("/")
def root():
    """Health check endpoint."""
    return {"message": "API is running", "version": settings.app_version}


# Include API routes
app.include_router(api_router, prefix="/api/v1")
