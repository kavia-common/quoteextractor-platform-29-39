from datetime import datetime
from typing import Dict, List, Tuple

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from src.api.models import ExportFormat, ExportJob, JobStatus, Quote
from src.api.store import EXPORT_JOBS, QUOTES, generate_id

router = APIRouter(tags=["exports"])

# In-memory storage for generated export outputs (job_id -> text or json string)
_EXPORT_OUTPUTS: Dict[str, Tuple[str, str]] = {}
# Tuple stored as (mime_type, content_string)


class ExportCreateRequest(BaseModel):
    quote_ids: List[str] = Field(
        default_factory=list, description="Quotes to include in the export."
    )
    format: ExportFormat = Field(..., description="Target export format.")
    title: str | None = Field(
        default=None,
        description="Optional title used for blog/plain_text headers.",
    )
    author: str | None = Field(
        default=None,
        description="Optional author attribution used in blog/LinkedIn formatting.",
    )


class ExportResponse(BaseModel):
    export: ExportJob = Field(..., description="Created/processed export job metadata.")
    note: str | None = Field(
        default=None, description="Additional information about the generated output."
    )


# PUBLIC_INTERFACE
@router.post(
    "",
    summary="Create export job",
    description=(
        "Create a new export job and generate platform-formatted output. "
        "MVP processes synchronously and stores results in-memory."
    ),
    response_model=ExportResponse,
    responses={
        201: {"description": "Export created and completed."},
        400: {"description": "Invalid request."},
        404: {"description": "Referenced quote not found."},
    },
    status_code=201,
)
def create_export_job(payload: ExportCreateRequest) -> ExportResponse:
    """
    PUBLIC_INTERFACE
    Create an export job, format content for the selected platform, and persist the output in-memory.

    Parameters:
        payload (ExportCreateRequest): The job request including quote IDs and format. Optional title/author.

    Returns:
        ExportResponse: Completed job metadata and a note.
    """
    # Validate quotes exist and collect them
    quotes: List[Quote] = []
    for qid in payload.quote_ids:
        q = QUOTES.get(qid)
        if not q:
            raise HTTPException(status_code=404, detail=f"Quote not found: {qid}")
        quotes.append(q)

    # Create job as processing
    job_id = generate_id("export")
    job = ExportJob(
        id=job_id,
        quote_ids=payload.quote_ids,
        format=payload.format,
        status=JobStatus.processing,
    )

    # Generate formatted output
    try:
        mime, output_text = _generate_output(payload.format, quotes, payload.title, payload.author)
        # Store output in memory and mark job complete
        _EXPORT_OUTPUTS[job_id] = (mime, output_text)
        job.status = JobStatus.completed
        job.result_url = f"/api/exports/{job_id}"  # self-link to fetch the job (and output via query)
        job.updated_at = datetime.utcnow()
        EXPORT_JOBS[job_id] = job
        return ExportResponse(export=job, note=f"Output generated in-memory as {mime}. Retrieve via GET /api/exports/{job_id}?download=1")
    except Exception as exc:  # pragma: no cover - generic safety
        job.status = JobStatus.failed
        job.error_message = str(exc)
        job.updated_at = datetime.utcnow()
        EXPORT_JOBS[job_id] = job
        raise HTTPException(status_code=500, detail=f"Failed to generate export: {exc}") from exc


# PUBLIC_INTERFACE
@router.get(
    "",
    summary="List export jobs",
    description="List all export jobs (MVP in-memory).",
)
def list_export_jobs():
    """
    PUBLIC_INTERFACE
    List export jobs.
    """
    return {"items": list(EXPORT_JOBS.values())}


# PUBLIC_INTERFACE
@router.get(
    "/{job_id}",
    summary="Get export job",
    description=(
        "Get export job by ID. "
        "Optionally return the generated output by passing download=1. "
        "For text outputs, returns plain text; for JSON returns application/json."
    ),
    responses={
        200: {"description": "Export job metadata or raw output if download=1."},
        404: {"description": "Export job not found."},
    },
)
def get_export_job(job_id: str, download: int | None = None):
    """
    PUBLIC_INTERFACE
    Get export job metadata by ID. If download=1, returns the raw generated output.

    Parameters:
        job_id (str): Export job identifier.
        download (int, optional): If 1, return the output content with appropriate MIME type.

    Returns:
        ExportJob or Response: Job metadata or the output content.
    """
    job = EXPORT_JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Export job not found")

    if download == 1:
        stored = _EXPORT_OUTPUTS.get(job_id)
        if not stored:
            raise HTTPException(status_code=404, detail="Export output not found")
        mime, content = stored
        # FastAPI Response import local to avoid polluting module namespace if unused
        from fastapi import Response

        return Response(content=content, media_type=mime)

    return job


def _generate_output(fmt: ExportFormat, quotes: List[Quote], title: str | None, author: str | None) -> Tuple[str, str]:
    """
    Generate platform-specific output from the quotes.

    Returns:
        (mime_type, content_text)
    """
    if fmt == ExportFormat.json:
        import json

        payload = {
            "title": title,
            "author": author,
            "quotes": [q.model_dump() for q in quotes],
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }
        return "application/json", json.dumps(payload, indent=2)
    if fmt in (ExportFormat.plain_text, ExportFormat.linkedin, ExportFormat.twitter):
        text = _format_text(fmt, quotes, title=title, author=author)
        return "text/plain; charset=utf-8", text
    if fmt == ExportFormat.instagram:
        text = _format_instagram(quotes)
        return "text/plain; charset=utf-8", text
    if fmt == ExportFormat.srt:
        text = _format_srt(quotes)
        return "text/plain; charset=utf-8", text
    if fmt == ExportFormat.vtt:
        text = _format_vtt(quotes)
        return "text/vtt; charset=utf-8", text

    # Default fallback
    return "text/plain; charset=utf-8", _format_text(ExportFormat.plain_text, quotes, title=title, author=author)


def _format_text(fmt: ExportFormat, quotes: List[Quote], title: str | None = None, author: str | None = None) -> str:
    """
    Basic formatting:
    - twitter: prefix with "X/Twitter", include hashtags if tags exist, keep lines under 280 chars by splitting
    - linkedin: professional tone, bullets, and attribution
    - plain_text: simple header + list
    """
    lines: List[str] = []
    header = ""

    if fmt == ExportFormat.twitter:
        header = "X/Twitter Export"
    elif fmt == ExportFormat.linkedin:
        header = "LinkedIn Export"
    else:
        header = title or "Quotes Export"

    if header:
        lines.append(header)
        lines.append("-" * len(header))

    if fmt == ExportFormat.twitter:
        # Each quote as a tweet-sized chunk. Not perfect word wrap, but keeps under limit roughly.
        for q in quotes:
            base = f"“{q.text.strip()}”"
            tags = ""
            if q.tags:
                # Include up to 2 tags to reduce length
                tags = " " + " ".join(f"#{t[:20]}" for t in q.tags[:2])
            tweet = (base + tags).strip()
            if len(tweet) > 275:
                tweet = tweet[:272] + "..."
            lines.append(tweet)
            lines.append("")  # spacer between tweets
    elif fmt == ExportFormat.linkedin:
        if author:
            lines.append(f"By {author}")
            lines.append("")
        lines.append("Highlights:")
        for q in quotes:
            snippet = q.text.strip()
            if len(snippet) > 400:
                snippet = snippet[:397] + "..."
            lines.append(f"• “{snippet}”")
        lines.append("")
        lines.append("Let me know your thoughts in the comments! #Leadership #Insights")
    else:  # plain_text
        if author:
            lines.append(f"Author: {author}")
            lines.append("")
        for idx, q in enumerate(quotes, start=1):
            lines.append(f"{idx}. “{q.text.strip()}”")
        if not quotes:
            lines.append("(No quotes selected)")

    return "\n".join(lines).rstrip() + "\n"


def _format_instagram(quotes: List[Quote]) -> str:
    """
    Simple Instagram caption style: emotive, short, with hashtags.
    """
    lines: List[str] = []
    lines.append("Instagram Export")
    lines.append("----------------")
    for q in quotes:
        caption = f"“{q.text.strip()}”"
        tag_line = ""
        if q.tags:
            tag_line = "\n" + " ".join(f"#{t[:20]}" for t in q.tags[:4])
        lines.append(caption + tag_line)
        lines.append("")  # space
    if not quotes:
        lines.append("(No quotes)")
    return "\n".join(lines).rstrip() + "\n"


def _format_srt(quotes: List[Quote]) -> str:
    """
    Create minimal SRT blocks from quotes (using start/end if available).
    """
    def fmt_time(seconds: float | None) -> str:
        if seconds is None:
            seconds = 0.0
        ms = int((seconds - int(seconds)) * 1000)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    lines: List[str] = []
    for idx, q in enumerate(quotes, start=1):
        lines.append(str(idx))
        lines.append(f"{fmt_time(q.start)} --> {fmt_time(q.end)}")
        lines.append(q.text.strip())
        lines.append("")  # blank line after each block
    return "\n".join(lines).rstrip() + "\n"


def _format_vtt(quotes: List[Quote]) -> str:
    """
    Create minimal WebVTT from quotes.
    """
    def fmt_time(seconds: float | None) -> str:
        if seconds is None:
            seconds = 0.0
        ms = int((seconds - int(seconds)) * 1000)
        h = int(seconds // 3600)
        m = int((seconds % 3600) // 60)
        s = int(seconds % 60)
        return f"{h:02}:{m:02}:{s:02}.{ms:03}"

    lines: List[str] = ["WEBVTT", ""]
    for q in quotes:
        lines.append(f"{fmt_time(q.start)} --> {fmt_time(q.end)}")
        lines.append(q.text.strip())
        lines.append("")  # blank
    return "\n".join(lines).rstrip() + "\n"


def _format_extension(fmt: ExportFormat) -> str:
    mapping = {
        ExportFormat.plain_text: "txt",
        ExportFormat.json: "json",
        ExportFormat.twitter: "txt",
        ExportFormat.linkedin: "txt",
        ExportFormat.instagram: "txt",
        ExportFormat.srt: "srt",
        ExportFormat.vtt: "vtt",
    }
    return mapping.get(fmt, "txt")
