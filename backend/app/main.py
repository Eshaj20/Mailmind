from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, health
from app.core.config import settings

# Create FastAPI application
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

# Add CORS middleware to the application
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,  # Allow specified origins from settings
        allow_credentials=True,
        allow_methods=["*"], # Allow all HTTP methods
        allow_headers=["*"], # Allow all headers
    )

# Include API routers for health and authentication endpoints
    app.include_router(health.router, prefix=settings.api_v1_prefix, tags=["health"])
    app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
    return app


app = create_app()

