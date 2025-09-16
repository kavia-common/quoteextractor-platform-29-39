from datetime import datetime
from typing import Optional
import time

from fastapi import APIRouter, BackgroundTasks, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from src.api.models import Asset, AssetType, JobStatus, Transcript
from src.api.store import ASSETS, TRANSCRIPTS, generate_id

router = APIRouter(tags=["uploads"])


class AssetCreateResponse(BaseModel):
    asset_id: str = Field(..., description="Unique ID of the registered asset.")
    status: str = Field(..., description="Initial processing status (queued).")
    note: Optional[str] = Field(None, description="Additional information about the processing.")
    asset: Optional[Asset] = Field(None, description="Registered asset metadata (MVP convenience).")


class UploadStatusResponse(BaseModel):
    asset_id: str = Field(..., description="Asset ID.")
    status: JobStatus = Field(..., description="Transcription processing status.")
    transcript_id: Optional[str] = Field(None, description="Transcript ID when available.")
    updated_at: datetime = Field(..., description="Last updated timestamp.")
    message: Optional[str] = Field(None, description="Status message.")


@router.post(
    "",
    summary="Register uploaded file",
    description="Accepts multipart/form-data (file + optional owner_id) and registers an Asset in-memory. "
                "Simulates a background transcription job.",
    response_model=AssetCreateResponse,
)
async def upload_asset(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(..., description="Binary file to upload."),
    owner_id: Optional[str] = Form(None, description="Owner user ID (MVP optional)."),
) -> AssetCreateResponse:
    """
    PUBLIC_INTERFACE
    Register a new uploaded asset and queue a simulated transcription job.

    Parameters:
        file (UploadFile): The uploaded media file (audio/video).
        owner_id (str, optional): Owner user id for tenancy (MVP optional).

    Returns:
        AssetCreateResponse: Registered asset id and queued status (plus metadata for convenience).
    """
    # MVP: we do not store file bytes; only capture metadata for the asset
    asset_id = generate_id("asset")
    asset = Asset(
        id=asset_id,
        filename=file.filename,
        content_type=file.content_type,
        asset_type=_infer_asset_type(file.content_type or ""),
        size_bytes=None,
        url=f"/mock/storage/{asset_id}/{file.filename}",
        owner_id=owner_id,
    )
    ASSETS[asset_id] = asset

    # Simulate async transcription creation via BackgroundTasks after delay
    background_tasks.add_task(_simulate_transcription_job_with_delay, asset_id)

    return AssetCreateResponse(
        asset_id=asset_id,
        status="queued",
        note="Transcription job queued (simulated).",
        asset=asset,
    )


@router.get(
    "/{asset_id}/status",
    summary="Get upload processing status",
    description="Returns the processing status (e.g., queued/processing/completed) for the asset's transcript.",
    response_model=UploadStatusResponse,
)
def get_upload_status(asset_id: str) -> UploadStatusResponse:
    """
    PUBLIC_INTERFACE
    Get the processing status for an uploaded asset.

    Args:
        asset_id (str): The asset identifier returned from the upload endpoint.

    Returns:
        UploadStatusResponse: Current processing status and related transcript id if available.
    """
    asset = ASSETS.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")

    # Find transcript for this asset (MVP: created shortly after upload)
    transcript = next((t for t in TRANSCRIPTS.values() if t.asset_id == asset_id), None)
    if not transcript:
        # Not yet created by background task
        return UploadStatusResponse(
            asset_id=asset_id,
            status=JobStatus.pending,
            transcript_id=None,
            updated_at=datetime.utcnow(),
            message="Queued",
        )

    return UploadStatusResponse(
        asset_id=asset_id,
        status=transcript.status,
        transcript_id=transcript.id,
        updated_at=transcript.updated_at,
        message="Processing" if transcript.status in {JobStatus.pending, JobStatus.processing} else "Done",
    )


@router.get(
    "",
    summary="List assets",
    description="List all registered assets (MVP in-memory).",
)
def list_assets():
    """
    PUBLIC_INTERFACE
    List all assets.

    Returns:
        dict: {"items": [Asset, ...]}
    """
    return {"items": list(ASSETS.values())}


@router.get(
    "/{asset_id}",
    summary="Get asset by ID",
    description="Fetch a single asset by ID.",
)
def get_asset(asset_id: str):
    """
    PUBLIC_INTERFACE
    Get a single asset.

    Args:
        asset_id (str): Asset ID

    Returns:
        Asset
    """
    asset = ASSETS.get(asset_id)
    if not asset:
        raise HTTPException(status_code=404, detail="Asset not found")
    return asset


def _infer_asset_type(content_type: str) -> AssetType:
    if content_type.startswith("audio/"):
        return AssetType.audio
    if content_type.startswith("video/"):
        return AssetType.video
    return AssetType.unknown


def _simulate_transcription_job_with_delay(asset_id: str) -> None:
    """
    Simulate a background task that, after a small delay, creates a Transcript record
    and marks it completed with a mock text.
    """
    # Short delay to simulate processing queue; keep small to avoid impacting CI.
    time.sleep(0.05)

    # Create transcript for asset if not exists
    existing = next((t for t in TRANSCRIPTS.values() if t.asset_id == asset_id), None)
    if existing:
        # If already present (from other flow), just ensure it's marked done
        existing.text = existing.text or f"Simulated transcript for asset {asset_id}."
        if existing.status in {JobStatus.pending, JobStatus.processing}:
            existing.status = JobStatus.completed
        existing.updated_at = datetime.utcnow()
        TRANSCRIPTS[existing.id] = existing
        return

    transcript_id = generate_id("transcript")
    transcript = Transcript(
        id=transcript_id,
        asset_id=asset_id,
        language=None,
        text=f"Simulated transcript for asset {asset_id}.",
        segments=[],
        status=JobStatus.completed,
    )
    TRANSCRIPTS[transcript_id] = transcript
