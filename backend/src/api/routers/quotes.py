from datetime import datetime
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from src.api.models import JobStatus, Quote, Transcript
from src.api.store import QUOTES, TRANSCRIPTS, ASSETS, generate_id

router = APIRouter(tags=["quotes"])


class QuoteCreateRequest(BaseModel):
    transcript_id: str = Field(..., description="Associated transcript ID.")
    text: str = Field(..., description="Quote text.")
    start: Optional[float] = Field(None, description="Start time in seconds.")
    end: Optional[float] = Field(None, description="End time in seconds.")
    confidence: Optional[float] = Field(None, description="AI confidence 0..1.")
    tags: list[str] = Field(default_factory=list, description="Tags.")


class QuoteResponse(BaseModel):
    quote: Quote


@router.post(
    "",
    summary="Create quote",
    description="Create a new quote from a transcript.",
    response_model=QuoteResponse,
)
def create_quote(payload: QuoteCreateRequest) -> QuoteResponse:
    """
    PUBLIC_INTERFACE
    Create a quote resource from a transcript.

    Parameters:
        payload (QuoteCreateRequest): Quote fields including transcript_id, text, timing, and tags.

    Returns:
        QuoteResponse: The created quote.
    """
    if payload.transcript_id not in TRANSCRIPTS:
        raise HTTPException(status_code=404, detail="Transcript not found")

    quote_id = generate_id("quote")
    quote = Quote(
        id=quote_id,
        transcript_id=payload.transcript_id,
        text=payload.text,
        start=payload.start,
        end=payload.end,
        confidence=payload.confidence,
        tags=payload.tags,
    )
    QUOTES[quote_id] = quote
    return QuoteResponse(quote=quote)


class QuoteExtractRequest(BaseModel):
    asset_id: Optional[str] = Field(
        None, description="If supplied, the transcript for this asset will be used."
    )
    transcript_id: Optional[str] = Field(
        None, description="If supplied, extract from this specific transcript."
    )
    text: Optional[str] = Field(
        None,
        description="Raw transcript text to extract from. If provided, takes precedence over asset/transcript.",
    )
    max_candidates: int = Field(
        default=5, description="Maximum number of mock quote candidates to generate."
    )
    min_length: int = Field(
        default=20, description="Minimum character length for a quote candidate."
    )


class QuoteExtractResponse(BaseModel):
    """Response containing the created quotes."""
    items: List[Quote] = Field(default_factory=list, description="Created quote items.")


@router.post(
    "/extract",
    summary="Extract quotes (mock)",
    description="Generate mock quote candidates from transcript text and store them in-memory.",
    response_model=QuoteExtractResponse,
)
def extract_quotes(payload: QuoteExtractRequest) -> QuoteExtractResponse:
    """
    PUBLIC_INTERFACE
    Generate mock quote candidates from transcript text and persist them in-memory.

    Behavior:
    - If 'text' is provided, it is used as the transcript content.
    - Else if 'transcript_id' is provided, that transcript is used.
    - Else if 'asset_id' is provided, the first transcript for that asset is used.
    - The function generates up to 'max_candidates' quotes from sentences longer than 'min_length'.

    Returns:
        QuoteExtractResponse: List of newly created Quote objects.
    """
    # Resolve source text and transcript relation
    source_text = None
    transcript_ref: Optional[Transcript] = None

    if payload.text:
        source_text = payload.text
        # create a temp transcript to attach quotes? For MVP, allow quotes without a real transcript by creating one?
        # We'll attach to an existing transcript if asset_id or transcript_id is provided; otherwise create a dummy transcript.
        if payload.transcript_id:
            transcript_ref = TRANSCRIPTS.get(payload.transcript_id)
            if not transcript_ref:
                raise HTTPException(status_code=404, detail="Transcript not found")
        elif payload.asset_id:
            transcript_ref = next((t for t in TRANSCRIPTS.values() if t.asset_id == payload.asset_id), None)
            if not transcript_ref:
                # If the asset exists but no transcript, create a minimal one with provided text for linkage.
                if payload.asset_id not in ASSETS:
                    raise HTTPException(status_code=404, detail="Asset not found")
                tid = generate_id("transcript")
                transcript_ref = Transcript(
                    id=tid,
                    asset_id=payload.asset_id,
                    language=None,
                    text=payload.text,
                    segments=[],
                    status=JobStatus.completed,
                )
                TRANSCRIPTS[tid] = transcript_ref
    elif payload.transcript_id:
        transcript_ref = TRANSCRIPTS.get(payload.transcript_id)
        if not transcript_ref:
            raise HTTPException(status_code=404, detail="Transcript not found")
        source_text = transcript_ref.text or ""
    elif payload.asset_id:
        transcript_ref = next((t for t in TRANSCRIPTS.values() if t.asset_id == payload.asset_id), None)
        if not transcript_ref:
            raise HTTPException(status_code=404, detail="Transcript not found for asset")
        source_text = transcript_ref.text or ""
    else:
        raise HTTPException(status_code=400, detail="Provide one of: text, transcript_id, or asset_id")

    # Simple sentence splitting heuristic for MVP
    sentences = _split_sentences(source_text)
    candidates: List[str] = [s.strip() for s in sentences if len(s.strip()) >= payload.min_length]

    created: List[Quote] = []
    for idx, sentence in enumerate(candidates[: max(0, payload.max_candidates)]):
        qid = generate_id("quote")
        quote = Quote(
            id=qid,
            transcript_id=(transcript_ref.id if transcript_ref else "transcript_0"),
            text=sentence,
            # mock timings: sequential 5s windows
            start=float(idx * 5),
            end=float(idx * 5 + 5),
            confidence=max(0.5, min(0.99, 0.5 + 0.1 * (idx % 5))),
            approved=False,
            tags=[],
        )
        QUOTES[qid] = quote
        created.append(quote)

    return QuoteExtractResponse(items=created)


@router.get(
    "",
    summary="List quotes",
    description="List quotes with optional filters: assetId, status (approved/pending), minConfidence.",
)
def list_quotes(
    assetId: Optional[str] = Query(
        default=None, description="Filter quotes linked to transcripts of this asset."
    ),
    status: Optional[str] = Query(
        default=None, description="Filter by approval status: 'approved' or 'pending'."
    ),
    minConfidence: Optional[float] = Query(
        default=None, ge=0.0, le=1.0, description="Minimum confidence score (0..1)."
    ),
):
    """
    PUBLIC_INTERFACE
    List quotes with filters.

    Parameters:
        assetId (str, optional): Only quotes whose transcript belongs to this asset.
        status (str, optional): 'approved' to include only approved quotes, 'pending' for not approved.
        minConfidence (float, optional): Minimum confidence threshold.

    Returns:
        dict: {"items": [Quote, ...]}
    """
    items = list(QUOTES.values())

    # Filter by asset
    if assetId:
        transcript_ids = {t.id for t in TRANSCRIPTS.values() if t.asset_id == assetId}
        items = [q for q in items if q.transcript_id in transcript_ids]

    # Filter by status
    if status:
        if status not in {"approved", "pending"}:
            raise HTTPException(status_code=400, detail="status must be 'approved' or 'pending'")
        want_approved = status == "approved"
        items = [q for q in items if bool(q.approved) == want_approved]

    # Filter by confidence
    if minConfidence is not None:
        items = [q for q in items if (q.confidence is not None and q.confidence >= minConfidence)]

    return {"items": items}


@router.get("/{quote_id}", summary="Get quote", description="Get a quote by ID.")
def get_quote(quote_id: str) -> Quote:
    """
    PUBLIC_INTERFACE
    Get quote by ID.
    """
    quote = QUOTES.get(quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")
    return quote


class QuoteUpdateRequest(BaseModel):
    text: Optional[str] = Field(None, description="Updated quote text.")
    start: Optional[float] = Field(None, description="Start time seconds.")
    end: Optional[float] = Field(None, description="End time seconds.")
    confidence: Optional[float] = Field(None, description="AI confidence.")
    approved: Optional[bool] = Field(None, description="Approval status.")
    tags: Optional[list[str]] = Field(None, description="Tags.")


@router.patch(
    "/{quote_id}",
    summary="Update/approve/reject quote",
    description="Update quote fields; can set approved=true/false for approve/reject.",
)
def update_quote(quote_id: str, payload: QuoteUpdateRequest) -> Quote:
    """
    PUBLIC_INTERFACE
    Update quote fields and approval status.

    Parameters:
        quote_id (str): The quote identifier.
        payload (QuoteUpdateRequest): Fields to update.

    Returns:
        Quote: The updated quote.
    """
    quote = QUOTES.get(quote_id)
    if not quote:
        raise HTTPException(status_code=404, detail="Quote not found")

    data = payload.model_dump(exclude_unset=True)
    for k, v in data.items():
        setattr(quote, k, v)
    quote.updated_at = datetime.utcnow()
    QUOTES[quote_id] = quote
    return quote


@router.delete("/{quote_id}", summary="Delete quote", description="Delete quote by ID.", status_code=204)
def delete_quote(quote_id: str):
    """
    PUBLIC_INTERFACE
    Delete quote by ID.
    """
    if quote_id not in QUOTES:
        raise HTTPException(status_code=404, detail="Quote not found")
    del QUOTES[quote_id]
    return None


def _split_sentences(text: str) -> List[str]:
    """
    Simple sentence splitting by common punctuation for MVP.
    """
    if not text:
        return []
    # Normalize whitespace
    normalized = " ".join(text.split())
    # Split by sentence enders
    sentences: List[str] = []
    current = []
    enders = {".", "!", "?"}
    for ch in normalized:
        current.append(ch)
        if ch in enders:
            s = "".join(current).strip()
            if s:
                sentences.append(s)
            current = []
    # Append tail if any
    tail = "".join(current).strip()
    if tail:
        sentences.append(tail)
    return sentences
