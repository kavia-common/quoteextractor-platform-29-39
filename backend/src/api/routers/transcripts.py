from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.models import JobStatus, Transcript, TranscriptSegment
from src.api.store import ASSETS, TRANSCRIPTS, generate_id

router = APIRouter(tags=["transcripts"])

# In-memory versioning and audit log for transcripts (MVP).
# Keyed by transcript_id.
_TRANSCRIPT_VERSIONS: dict[str, List[Transcript]] = {}
_TRANSCRIPT_AUDIT: dict[str, List[dict]] = {}


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
    # initialize versions/audit
    _TRANSCRIPT_VERSIONS[transcript_id] = [transcript.model_copy(deep=True)]
    _TRANSCRIPT_AUDIT[transcript_id] = [
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "create",
            "changes": transcript.model_dump(),
        }
    ]
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


@router.put(
    "/{transcript_id}",
    summary="Edit transcript (versioned)",
    description="Replace or edit transcript fields and store a new version with an audit log entry.",
)
def put_transcript(transcript_id: str, payload: TranscriptUpdateRequest) -> Transcript:
    """
    PUBLIC_INTERFACE
    Edit transcript values and keep an in-memory version history and audit log.

    Parameters:
        transcript_id (str): ID of the transcript to update.
        payload (TranscriptUpdateRequest): Fields to update (partial).

    Returns:
        Transcript: The updated transcript.
    """
    transcript = TRANSCRIPTS.get(transcript_id)
    if not transcript:
        raise HTTPException(status_code=404, detail="Transcript not found")

    before = transcript.model_dump()
    if payload.language is not None:
        transcript.language = payload.language
    if payload.text is not None:
        transcript.text = payload.text
    if payload.status is not None:
        transcript.status = payload.status
    transcript.updated_at = datetime.utcnow()
    TRANSCRIPTS[transcript_id] = transcript

    # Versioning
    _TRANSCRIPT_VERSIONS.setdefault(transcript_id, []).append(transcript.model_copy(deep=True))

    # Audit
    after = transcript.model_dump()
    changes = {k: {"before": before.get(k), "after": after.get(k)} for k in after.keys() if before.get(k) != after.get(k)}
    _TRANSCRIPT_AUDIT.setdefault(transcript_id, []).append(
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "update",
            "changes": changes,
        }
    )
    return transcript


@router.get(
    "/{transcript_id}/versions",
    summary="Get transcript versions",
    description="Return the in-memory version history for a transcript.",
)
def get_versions(transcript_id: str):
    """
    PUBLIC_INTERFACE
    Return version history for a transcript.
    """
    versions = _TRANSCRIPT_VERSIONS.get(transcript_id)
    if versions is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"count": len(versions), "versions": versions}


@router.get(
    "/{transcript_id}/audit",
    summary="Get transcript audit log",
    description="Return the in-memory audit log for a transcript.",
)
def get_audit(transcript_id: str):
    """
    PUBLIC_INTERFACE
    Return audit log for a transcript.
    """
    audit = _TRANSCRIPT_AUDIT.get(transcript_id)
    if audit is None:
        raise HTTPException(status_code=404, detail="Transcript not found")
    return {"items": audit}


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

    # Version + audit for segment append
    _TRANSCRIPT_VERSIONS.setdefault(transcript_id, []).append(transcript.model_copy(deep=True))
    _TRANSCRIPT_AUDIT.setdefault(transcript_id, []).append(
        {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "action": "append_segment",
            "changes": {"segments": "appended"},
        }
    )
    return transcript
