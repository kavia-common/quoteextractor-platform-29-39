from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.models import Quote
from src.api.store import QUOTES, TRANSCRIPTS, generate_id

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


@router.post("", summary="Create quote", description="Create a new quote from a transcript.", response_model=QuoteResponse)
def create_quote(payload: QuoteCreateRequest) -> QuoteResponse:
    """
    PUBLIC_INTERFACE
    Create a quote resource from a transcript.
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


@router.get("", summary="List quotes", description="List all quotes (MVP).")
def list_quotes():
    """
    PUBLIC_INTERFACE
    List quotes.
    """
    return {"items": list(QUOTES.values())}


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


@router.patch("/{quote_id}", summary="Update quote", description="Update a quote.")
def update_quote(quote_id: str, payload: QuoteUpdateRequest) -> Quote:
    """
    PUBLIC_INTERFACE
    Update quote fields.
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
