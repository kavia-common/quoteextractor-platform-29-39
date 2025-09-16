from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, EmailStr, Field

# NOTE: MVP uses simple string IDs. TODO: Replace with UUIDs from DB later.


class AssetType(str, Enum):
    audio = "audio"
    video = "video"
    unknown = "unknown"


class JobStatus(str, Enum):
    pending = "pending"
    processing = "processing"
    completed = "completed"
    failed = "failed"
    canceled = "canceled"


# PUBLIC_INTERFACE
class User(BaseModel):
    """Basic user profile (MVP). In production, integrate with real auth provider."""
    id: str = Field(..., description="User identifier (e.g., email or UUID).")
    email: EmailStr = Field(..., description="User email.")
    name: Optional[str] = Field(None, description="Display name.")


# PUBLIC_INTERFACE
class Asset(BaseModel):
    """Ingested media asset representing an uploaded file."""
    id: str = Field(..., description="Asset ID.")
    filename: str = Field(..., description="Original file name.")
    content_type: Optional[str] = Field(None, description="MIME type.")
    asset_type: AssetType = Field(default=AssetType.unknown, description="Asset content category.")
    size_bytes: Optional[int] = Field(None, description="File size in bytes.")
    url: Optional[str] = Field(None, description="Storage URL (MVP: placeholder/local path).")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp.")
    owner_id: Optional[str] = Field(None, description="User ID of the owner/creator.")


# PUBLIC_INTERFACE
class TranscriptSegment(BaseModel):
    """Segment within a transcript with timing info."""
    start: float = Field(..., description="Start time in seconds.")
    end: float = Field(..., description="End time in seconds.")
    text: str = Field(..., description="Text content for the segment.")
    speaker: Optional[str] = Field(None, description="Speaker label if available.")


# PUBLIC_INTERFACE
class Transcript(BaseModel):
    """Transcript associated with an asset."""
    id: str = Field(..., description="Transcript ID.")
    asset_id: str = Field(..., description="Associated asset ID.")
    language: Optional[str] = Field(None, description="Language code (BCP-47).")
    text: Optional[str] = Field(None, description="Full transcript text.")
    segments: List[TranscriptSegment] = Field(default_factory=list, description="Segmented transcript.")
    status: JobStatus = Field(default=JobStatus.pending, description="Processing status.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp.")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp.")


# PUBLIC_INTERFACE
class Quote(BaseModel):
    """A quote extracted from a transcript."""
    id: str = Field(..., description="Quote ID.")
    transcript_id: str = Field(..., description="Associated transcript ID.")
    start: Optional[float] = Field(None, description="Start time in seconds in the media.")
    end: Optional[float] = Field(None, description="End time in seconds in the media.")
    text: str = Field(..., description="Quote text.")
    confidence: Optional[float] = Field(None, description="AI confidence score 0..1.")
    approved: bool = Field(default=False, description="Marked as approved by reviewer.")
    tags: List[str] = Field(default_factory=list, description="Free-form tags.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp.")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp.")


# PUBLIC_INTERFACE
class ExportFormat(str, Enum):
    """Supported export formats."""
    plain_text = "plain_text"
    json = "json"
    twitter = "twitter"
    linkedin = "linkedin"
    instagram = "instagram"
    srt = "srt"
    vtt = "vtt"


# PUBLIC_INTERFACE
class ExportJob(BaseModel):
    """Represents an export request and its lifecycle."""
    id: str = Field(..., description="Export job ID.")
    quote_ids: List[str] = Field(default_factory=list, description="Quotes to include in the export.")
    format: ExportFormat = Field(..., description="Target export format.")
    status: JobStatus = Field(default=JobStatus.pending, description="Job processing status.")
    result_url: Optional[str] = Field(None, description="URL to download the exported content.")
    error_message: Optional[str] = Field(None, description="Error details if job failed.")
    created_at: datetime = Field(default_factory=datetime.utcnow, description="Creation timestamp.")
    updated_at: datetime = Field(default_factory=datetime.utcnow, description="Last update timestamp.")
