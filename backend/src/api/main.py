from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers.uploads import router as uploads_router
from src.api.routers.transcripts import router as transcripts_router
from src.api.routers.quotes import router as quotes_router
from src.api.routers.exports import router as exports_router
from src.api.routers.status import router as status_router
from src.api.routers.auth import router as auth_router

# Initialize FastAPI with metadata for OpenAPI
app = FastAPI(
    title="Quote Extraction Platform API",
    description=(
        "Backend API for ingesting media, generating transcripts, extracting quotes, "
        "managing review workflows, and exporting platform-specific content.\n\n"
        "Real-time usage notes:\n"
        "- MVP does not expose WebSocket endpoints; background tasks are simulated.\n"
        "- Transcripts support GET by ID and PUT edits with in-memory versioning and audit logs."
    ),
    version="0.1.0",
    contact={"name": "QuoteExtractor Team"},
    license_info={"name": "Proprietary"},
    openapi_tags=[
        {"name": "uploads", "description": "Upload media files and register assets."},
        {"name": "transcripts", "description": "Create and manage transcripts."},
        {"name": "quotes", "description": "AI-extracted quotes and manual curation."},
        {"name": "exports", "description": "Export jobs to various formats/platforms."},
        {"name": "status", "description": "Service and job status endpoints."},
        {"name": "health", "description": "Health check endpoints."},
        {"name": "auth", "description": "Authentication endpoints (MVP mock)."},
    ],
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # TODO: Restrict in production via ENV var
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/", tags=["health"], summary="Health check", description="Returns service health status.")
def health_check():
    """
    PUBLIC_INTERFACE
    Returns a simple health status payload.

    Returns:
        dict: {"message": "Healthy"}
    """
    return {"message": "Healthy"}

# Route registration
app.include_router(uploads_router, prefix="/api/uploads")
app.include_router(transcripts_router, prefix="/api/transcripts")
app.include_router(quotes_router, prefix="/api/quotes")
app.include_router(exports_router, prefix="/api/exports")
app.include_router(status_router, prefix="/api/status")
app.include_router(auth_router, prefix="/auth")
