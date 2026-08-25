from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import auth, gmail, health
from app.core.config import settings

# Create and configure the FastAPI application, including middleware for CORS and registering API routes for health checks, authentication, and Gmail integration.
def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.project_name,
        version="0.1.0",
        openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    )

# Add CORS middleware to the FastAPI application, allowing cross-origin requests from the specified origins in the settings, and enabling credentials, methods, and headers for all requests.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Include the API routers for health checks, authentication, and Gmail integration in the FastAPI application, using the specified prefixes and tags for each route group.
    app.include_router(health.router, prefix=settings.api_v1_prefix, tags=["health"])
    app.include_router(auth.router, prefix=f"{settings.api_v1_prefix}/auth", tags=["auth"])
    app.include_router(gmail.router, prefix=f"{settings.api_v1_prefix}/gmail", tags=["gmail"])
    return app


app = create_app()
