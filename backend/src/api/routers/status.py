from datetime import datetime

from fastapi import APIRouter

from src.api.store import ASSETS, EXPORT_JOBS, QUOTES, TRANSCRIPTS, USERS

router = APIRouter(tags=["status"])


@router.get("", summary="Service status", description="Basic service status and in-memory counts.")
def service_status():
    """
    PUBLIC_INTERFACE
    Returns service status and counts of in-memory resources.

    Returns:
        dict: status info
    """
    return {
        "service": "Quote Extraction Platform",
        "server_time": datetime.utcnow().isoformat() + "Z",
        "counts": {
            "users": len(USERS),
            "assets": len(ASSETS),
            "transcripts": len(TRANSCRIPTS),
            "quotes": len(QUOTES),
            "exports": len(EXPORT_JOBS),
        },
        "notes": [
            "MVP uses in-memory stores; data resets on restart.",
            "TODO: integrate database and real authentication.",
        ],
    }
