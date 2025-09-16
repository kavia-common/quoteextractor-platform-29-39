from datetime import datetime
from typing import Optional

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

    # Create an associated transcript record in 'processing' to represent queued work
    transcript_id = generate_id("transcript")
    transcript = Transcript(
        id=transcript_id,
        asset_id=asset_id,
        language=None,
        text=None,
        segments=[],
        status=JobStatus.processing,
    )
    TRANSCRIPTS[transcript_id] = transcript

    # Simulate async transcription completion via BackgroundTasks
    background_tasks.add_task(_simulate_transcription_job, transcript_id)

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

    # Find transcript for this asset (MVP: 1:1 created at upload time)
    transcript = next((t for t in TRANSCRIPTS.values() if t.asset_id == asset_id), None)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not initialized for this asset")

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


def _simulate_transcription_job(transcript_id: str) -> None:
    """
    Simulate background transcription work. This function marks the transcript as completed
    and writes a simple placeholder transcript text.

    In a real system, this would:
      - Store the file to object storage
      - Call an ASR/transcription provider
      - Poll or stream results, then persist transcript and segments
    """
    # A tiny synchronous delay simulation can be done by time.sleep, but we avoid blocking here.
    # Instead, just complete immediately to keep CI quick and deterministic.
    transcript = TRANSCRIPTS.get(transcript_id)
    if not transcript:
        return
    transcript.text = f"Simulated transcript for asset {transcript.asset_id}."
    transcript.status = JobStatus.completed
    transcript.updated_at = datetime.utcnow()
    TRANSCRIPTS[transcript_id] = transcript
