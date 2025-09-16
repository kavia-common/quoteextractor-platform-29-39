from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.models import JobStatus, Transcript, TranscriptSegment
from src.api.store import ASSETS, TRANSCRIPTS, generate_id

router = APIRouter(tags=["transcripts"])


class TranscriptCreateRequest(BaseModel):
    asset_id: str = Field(..., description="ID of the asset to transcribe.")
    language: Optional[str] = Field(None, description="Language code (BCP-47).")
    text: Optional[str] = Field(None, description="Full transcript text (manual or precomputed).")


class TranscriptResponse(BaseModel):
    transcript: Transcript


@router.post(
    "",
    summary="Create transcript",
    description="Creates a new transcript record for an asset (MVP in-memory).",
    response_model=TranscriptResponse,
)
def create_transcript(payload: TranscriptCreateRequest) -> TranscriptResponse:
    """
    PUBLIC_INTERFACE
    Create a transcript for an asset.
    """
    if payload.asset_id not in ASSETS:
        raise HTTPException(status_code=404, detail="Asset not found")

    transcript_id = generate_id("transcript")
    transcript = Transcript(
        id=transcript_id,
        asset_id=payload.asset_id,
        language=payload.language,
        text=payload.text,
        segments=[],
        status=JobStatus.completed if payload.text else JobStatus.pending,
    )
    TRANSCRIPTS[transcript_id] = transcript
    return TranscriptResponse(transcript=transcript)


@router.get("", summary="List transcripts", description="List all transcripts.")
def list_transcripts():
    """
    PUBLIC_INTERFACE
    List transcripts.
    """
    return {"items": list(TRANSCRIPTS.values())}


@router.get("/{transcript_id}", summary="Get transcript", description="Fetch a transcript by ID.")
def get_transcript(transcript_id: str) -> Transcript:
    """
    PUBLIC_INTERFACE
    Get transcript by ID.
    """
    transcript = TRANSCRIPTS.get(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return transcript


class TranscriptUpdateRequest(BaseModel):
    language: Optional[str] = Field(None, description="Language code (BCP-47).")
    text: Optional[str] = Field(None, description="Full transcript text.")
    status: Optional[JobStatus] = Field(None, description="Processing status.")


@router.patch("/{transcript_id}", summary="Update transcript", description="Update basic fields of a transcript.")
def update_transcript(transcript_id: str, payload: TranscriptUpdateRequest) -> Transcript:
    """
    PUBLIC_INTERFACE
    Update transcript values.
    """
    transcript = TRANSCRIPTS.get(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    if payload.language is not None:
        transcript.language = payload.language
    if payload.text is not None:
        transcript.text = payload.text
    if payload.status is not None:
        transcript.status = payload.status
    transcript.updated_at = datetime.utcnow()
    TRANSCRIPTS[transcript_id] = transcript
    return transcript


class SegmentAppendRequest(BaseModel):
    start: float = Field(..., description="Start time in seconds.")
    end: float = Field(..., description="End time in seconds.")
    text: str = Field(..., description="Segment text.")
    speaker: Optional[str] = Field(None, description="Speaker label.")


@router.post("/{transcript_id}/segments", summary="Append segment", description="Append a new segment to a transcript.")
def append_segment(transcript_id: str, payload: SegmentAppendRequest) -> Transcript:
    """
    PUBLIC_INTERFACE
    Append a segment to transcript.
    """
    transcript = TRANSCRIPTS.get(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    segment = TranscriptSegment(**payload.model_dump())
    transcript.segments.append(segment)
    transcript.updated_at = datetime.utcnow()
    TRANSCRIPTS[transcript_id] = transcript
    return transcript
